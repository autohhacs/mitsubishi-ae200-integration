"""Mitsubishi AE200 communication library."""
import logging
import websockets
from websockets.extensions import permessage_deflate
import xml.etree.ElementTree as ET
import base64

_LOGGER = logging.getLogger(__name__)

# XML payloads for communication
getUnitsPayload = """<?xml version="1.0" encoding="UTF-8" ?>
<Packet>
<Command>getRequest</Command>
<DatabaseManager>
<ControlGroup>
<MnetList />
</ControlGroup>
</DatabaseManager>
</Packet>
"""


def getMnetDetails(deviceIds):
    """Generate XML payload for getting device details."""
    mnets = "\n".join([
        f'<Mnet Group="{deviceId}" Drive="*" Mode="*" SetTemp="*" SetTemp1="*" '
        f'SetTemp2="*" InletTemp="*" AirDirection="*" FanSpeed="*" />'
        for deviceId in deviceIds
    ])
    
    return f"""<?xml version="1.0" encoding="UTF-8" ?>
<Packet>
<Command>getRequest</Command>
<DatabaseManager>
{mnets}
</DatabaseManager>
</Packet>
"""


class MitsubishiAE200Functions:
    """Handle communication with Mitsubishi AE200 controller."""

    def __init__(self):
        """Initialize the communication handler."""
        self._authenticated = False

    def _create_auth_header(self, username: str, password: str) -> str:
        """Create basic auth header."""
        credentials = f"{username}:{password}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded_credentials}"

    def _get_connection_params(self, address: str, username: str = None, password: str = None):
        """Get websocket connection parameters."""
        params = {
            "uri": f"ws://{address}/b_xmlproc/",
            "extensions": [permessage_deflate.ClientPerMessageDeflateFactory()],
            "origin": f'http://{address}',
            "subprotocols": ['b_xmlproc'],
            "ping_timeout": 10,
            "close_timeout": 10
        }
        
        if username and password:
            auth_header = self._create_auth_header(username, password)
            params["extra_headers"] = {"Authorization": auth_header}

        return params

    async def authenticate(self, address: str, username: str, password: str) -> bool:
        """Test authentication with the AE200 controller."""
        try:
            _LOGGER.info(f"Testing authentication to {address}")
            params = self._get_connection_params(address, username, password)
            
            async with websockets.connect(**params) as websocket:
                # Send a test request to verify connection
                await websocket.send(getUnitsPayload)
                response = await websocket.recv()
                
                # If we get a response, authentication succeeded
                _LOGGER.info(f"Authentication successful for AE200 controller at {address}")
                return True
                    
        except websockets.exceptions.ConnectionClosedError as e:
            _LOGGER.error(f"Connection closed during authentication: {e}")
            return False
        except Exception as e:
            _LOGGER.error(f"Authentication error for {address}: {e}")
            return False

    async def getDevicesAsync(self, address: str, username: str = None, password: str = None):
        """Get list of devices from the controller."""
        try:
            _LOGGER.info(f"Getting devices from controller at {address}")
            params = self._get_connection_params(address, username, password)
            
            async with websockets.connect(**params) as websocket:
                await websocket.send(getUnitsPayload)
                unitsResultStr = await websocket.recv()
                
                _LOGGER.debug(f"Raw device list response: {unitsResultStr}")
                
                unitsResultXML = ET.fromstring(unitsResultStr)

                groupList = []
                for r in unitsResultXML.findall('./DatabaseManager/ControlGroup/MnetList/MnetRecord'):
                    group_id = r.get('Group')
                    group_name = r.get('GroupNameWeb')
                    if group_id and group_name:
                        groupList.append({
                            "id": group_id,
                            "name": group_name
                        })

                _LOGGER.info(f"Found {len(groupList)} devices on controller {address}: {groupList}")
                return groupList
                
        except Exception as e:
            _LOGGER.error(f"Error getting devices from {address}: {e}")
            raise

    async def getDeviceInfoAsync(self, address: str, deviceId: str, username: str = None, password: str = None):
        """Get detailed information for a specific device."""
        try:
            params = self._get_connection_params(address, username, password)
            
            async with websockets.connect(**params) as websocket:
                getMnetDetailsPayload = getMnetDetails([deviceId])
                await websocket.send(getMnetDetailsPayload)
                mnetDetailsResultStr = await websocket.recv()
                
                _LOGGER.debug(f"Device {deviceId} raw response: {mnetDetailsResultStr}")
                
                mnetDetailsResultXML = ET.fromstring(mnetDetailsResultStr)
                node = mnetDetailsResultXML.find('./DatabaseManager/Mnet')
                
                if node is not None:
                    return node.attrib
                else:
                    _LOGGER.warning(f"No device data found for device {deviceId}")
                    return {}
                    
        except Exception as e:
            _LOGGER.error(f"Error getting device info for {deviceId} on {address}: {e}")
            raise

    async def sendAsync(self, address: str, deviceId: str, attributes: dict, username: str = None, password: str = None):
        """Send commands to a specific device."""
        try:
            params = self._get_connection_params(address, username, password)
            
            async with websockets.connect(**params) as websocket:
                attrs = " ".join([f'{key}="{attributes[key]}"' for key in attributes])
                payload = f"""<?xml version="1.0" encoding="UTF-8" ?>
<Packet>
<Command>setRequest</Command>
<DatabaseManager>
<Mnet Group="{deviceId}" {attrs}  />
</DatabaseManager>
</Packet>
"""
                _LOGGER.info(f"Sending command to device {deviceId}: {attributes}")
                _LOGGER.debug(f"Full payload: {payload}")
                
                await websocket.send(payload)
                
                # Wait for response to confirm command was received
                response = await websocket.recv()
                _LOGGER.debug(f"Command response for device {deviceId}: {response}")
                
                # Parse response to check for errors
                try:
                    root = ET.fromstring(response)
                    error_node = root.find('.//Error')
                    if error_node is not None:
                        error_msg = error_node.get('Message', 'Unknown error')
                        _LOGGER.error(f"Device command error: {error_msg}")
                        raise Exception(f"Device command failed: {error_msg}")
                except ET.ParseError:
                    # If we can't parse the response, assume success
                    pass
                    
        except Exception as e:
            _LOGGER.error(f"Error sending command to device {deviceId} on {address}: {e}")
            raise