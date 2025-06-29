import logging
import asyncio
import websockets
from websockets.extensions import permessage_deflate
import xml.etree.ElementTree as ET
import base64
import hashlib

_LOGGER = logging.getLogger(__name__)

# XML payloads for authentication
loginPayload = """<?xml version="1.0" encoding="UTF-8" ?>
<Packet>
<Command>getRequest</Command>
<DatabaseManager>
<Mnet Group="*" Drive="*" />
</DatabaseManager>
</Packet>
"""

# Payload to get units/devices
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
        f'<Mnet Group="{deviceId}" Drive="*" Vent24h="*" Mode="*" VentMode="*" '
        f'ModeStatus="*" SetTemp="*" SetTemp1="*" SetTemp2="*" SetTemp3="*" '
        f'SetTemp4="*" SetTemp5="*" SetHumidity="*" InletTemp="*" InletHumidity="*" '
        f'AirDirection="*" FanSpeed="*" RemoCon="*" DriveItem="*" ModeItem="*" '
        f'SetTempItem="*" FilterItem="*" AirDirItem="*" FanSpeedItem="*" TimerItem="*" '
        f'CheckWaterItem="*" FilterSign="*" Hold="*" EnergyControl="*" EnergyControlIC="*" '
        f'SetbackControl="*" Ventilation="*" VentiDrive="*" VentiFan="*" Schedule="*" '
        f'ScheduleAvail="*" ErrorSign="*" CheckWater="*" TempLimitCool="*" TempLimitHeat="*" '
        f'TempLimit="*" CoolMin="*" CoolMax="*" HeatMin="*" HeatMax="*" AutoMin="*" '
        f'AutoMax="*" TurnOff="*" MaxSaveValue="*" RoomHumidity="*" Brightness="*" '
        f'Occupancy="*" NightPurge="*" Humid="*" Vent24hMode="*" SnowFanMode="*" '
        f'InletTempHWHP="*" OutletTempHWHP="*" HeadTempHWHP="*" OutdoorTemp="*" '
        f'BrineTemp="*" HeadInletTempCH="*" BACnetTurnOff="*" AISmartStart="*"  />'
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
    def __init__(self):
        self._authenticated = False
        self._auth_token = None
        self._session_id = None

    def _create_auth_header(self, username: str, password: str) -> str:
        """Create basic auth header."""
        credentials = f"{username}:{password}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded_credentials}"

    async def authenticate(self, address: str, username: str, password: str) -> bool:
        """Authenticate with the AE200 controller."""
        try:
            # Create authentication headers
            auth_header = self._create_auth_header(username, password)
            extra_headers = {
                "Authorization": auth_header,
                "User-Agent": "Home Assistant Mitsubishi AE200 Integration"
            }

            async with websockets.connect(
                f"ws://{address}/b_xmlproc/",
                extensions=[permessage_deflate.ClientPerMessageDeflateFactory()],
                origin=f'http://{address}',
                subprotocols=['b_xmlproc'],
                extra_headers=extra_headers
            ) as websocket:
                
                # Send a test request to verify authentication
                await websocket.send(loginPayload)
                response = await websocket.recv()
                
                # Parse response to check if authentication was successful
                try:
                    root = ET.fromstring(response)
                    # If we get a valid response without error, authentication succeeded
                    self._authenticated = True
                    _LOGGER.info("Authentication successful for AE200 controller at %s", address)
                    return True
                except ET.ParseError:
                    _LOGGER.error("Failed to parse authentication response")
                    return False
                    
        except websockets.exceptions.ConnectionClosedError as e:
            if e.code == 1002:  # Protocol error, likely auth failure
                _LOGGER.error("Authentication failed - invalid credentials")
                return False
            raise
        except Exception as e:
            _LOGGER.error("Authentication error: %s", str(e))
            return False

    async def _get_authenticated_websocket(self, address: str, username: str = None, password: str = None):
        """Get an authenticated websocket connection."""
        extra_headers = {}
        
        if username and password:
            auth_header = self._create_auth_header(username, password)
            extra_headers["Authorization"] = auth_header
            extra_headers["User-Agent"] = "Home Assistant Mitsubishi AE200 Integration"

        return await websockets.connect(
            f"ws://{address}/b_xmlproc/",
            extensions=[permessage_deflate.ClientPerMessageDeflateFactory()],
            origin=f'http://{address}',
            subprotocols=['b_xmlproc'],
            extra_headers=extra_headers if extra_headers else None
        )

    async def getDevicesAsync(self, address: str, username: str = None, password: str = None):
        """Get list of devices from the controller."""
        try:
            async with self._get_authenticated_websocket(address, username, password) as websocket:
                await websocket.send(getUnitsPayload)
                unitsResultStr = await websocket.recv()
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

                _LOGGER.debug("Found %d devices on controller %s", len(groupList), address)
                return groupList
                
        except Exception as e:
            _LOGGER.error("Error getting devices from %s: %s", address, str(e))
            raise

    async def getDeviceInfoAsync(self, address: str, deviceId: str, username: str = None, password: str = None):
        """Get detailed information for a specific device."""
        try:
            async with self._get_authenticated_websocket(address, username, password) as websocket:
                getMnetDetailsPayload = getMnetDetails([deviceId])
                await websocket.send(getMnetDetailsPayload)
                mnetDetailsResultStr = await websocket.recv()
                
                _LOGGER.debug("Device %s raw response: %s", deviceId, mnetDetailsResultStr)
                
                mnetDetailsResultXML = ET.fromstring(mnetDetailsResultStr)
                node = mnetDetailsResultXML.find('./DatabaseManager/Mnet')
                
                if node is not None:
                    return node.attrib
                else:
                    _LOGGER.warning("No device data found for device %s", deviceId)
                    return {}
                    
        except Exception as e:
            _LOGGER.error("Error getting device info for %s on %s: %s", deviceId, address, str(e))
            raise

    async def sendAsync(self, address: str, deviceId: str, attributes: dict, username: str = None, password: str = None):
        """Send commands to a specific device."""
        try:
            async with self._get_authenticated_websocket(address, username, password) as websocket:
                attrs = " ".join([f'{key}="{attributes[key]}"' for key in attributes])
                payload = f"""<?xml version="1.0" encoding="UTF-8" ?>
<Packet>
<Command>setRequest</Command>
<DatabaseManager>
<Mnet Group="{deviceId}" {attrs}  />
</DatabaseManager>
</Packet>
"""
                _LOGGER.debug("Sending command to device %s: %s", deviceId, payload)
                await websocket.send(payload)
                
                # Wait for response to confirm command was received
                response = await websocket.recv()
                _LOGGER.debug("Command response for device %s: %s", deviceId, response)
                
                # Parse response to check for errors
                try:
                    root = ET.fromstring(response)
                    error_node = root.find('.//Error')
                    if error_node is not None:
                        error_msg = error_node.get('Message', 'Unknown error')
                        _LOGGER.error("Device command error: %s", error_msg)
                        raise Exception(f"Device command failed: {error_msg}")
                except ET.ParseError:
                    # If we can't parse the response, assume success
                    pass
                    
        except Exception as e:
            _LOGGER.error("Error sending command to device %s on %s: %s", deviceId, address, str(e))
            raise
