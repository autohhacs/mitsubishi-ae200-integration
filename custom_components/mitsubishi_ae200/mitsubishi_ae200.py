import logging
import asyncio
import websockets
from websockets.extensions import permessage_deflate
import xml.etree.ElementTree as ET
from pprint import pprint

_LOGGER = logging.getLogger(**name**)

getUnitsPayload = “””<?xml version="1.0" encoding="UTF-8" ?>
<Packet>
<Command>getRequest</Command>
<DatabaseManager>
<ControlGroup>
<MnetList />
</ControlGroup>
</DatabaseManager>
</Packet>
“””

def getMnetDetails(deviceIds):
mnets = “\n”.join([f’<Mnet Group="{deviceId}" Drive="*" Vent24h="*" Mode="*" VentMode="*" ModeStatus="*" SetTemp="*" SetTemp1="*" SetTemp2="*" SetTemp3="*" SetTemp4="*" SetTemp5="*" SetHumidity="*" InletTemp="*" InletHumidity="*" AirDirection="*" FanSpeed="*" RemoCon="*" DriveItem="*" ModeItem="*" SetTempItem="*" FilterItem="*" AirDirItem="*" FanSpeedItem="*" TimerItem="*" CheckWaterItem="*" FilterSign="*" Hold="*" EnergyControl="*" EnergyControlIC="*" SetbackControl="*" Ventilation="*" VentiDrive="*" VentiFan="*" Schedule="*" ScheduleAvail="*" ErrorSign="*" CheckWater="*" TempLimitCool="*" TempLimitHeat="*" TempLimit="*" CoolMin="*" CoolMax="*" HeatMin="*" HeatMax="*" AutoMin="*" AutoMax="*" TurnOff="*" MaxSaveValue="*" RoomHumidity="*" Brightness="*" Occupancy="*" NightPurge="*" Humid="*" Vent24hMode="*" SnowFanMode="*" InletTempHWHP="*" OutletTempHWHP="*" HeadTempHWHP="*" OutdoorTemp="*" BrineTemp="*" HeadInletTempCH="*" BACnetTurnOff="*" AISmartStart="*"  />’ for deviceId in deviceIds])
return f”””<?xml version="1.0" encoding="UTF-8" ?>
<Packet>
<Command>getRequest</Command>
<DatabaseManager>
{mnets}
</DatabaseManager>
</Packet>
“””

class MitsubishiAE200Functions:
def **init**(self):
self._json = None
self._temp_list = []

```
async def getDevicesAsync(self, address):
    _LOGGER.info(f"Getting devices from {address}")
    try:
        async with websockets.connect(
                f"ws://{address}/b_xmlproc/",
                extensions=[permessage_deflate.ClientPerMessageDeflateFactory()],
                origin=f'http://{address}',
                subprotocols=['b_xmlproc'],
                timeout=10  # Add timeout
            ) as websocket:

            _LOGGER.debug(f"Connected to websocket at {address}")
            await websocket.send(getUnitsPayload)
            unitsResultStr = await websocket.recv()
            _LOGGER.debug(f"Received device list response: {unitsResultStr[:200]}...")
            
            unitsResultXML = ET.fromstring(unitsResultStr)

            groupList = []
            for r in unitsResultXML.findall('./DatabaseManager/ControlGroup/MnetList/MnetRecord'):
                groupList.append({
                    "id": r.get('Group'),
                    "name": r.get('GroupNameWeb')
                })

            await websocket.close()
            _LOGGER.info(f"Found {len(groupList)} devices")
            return groupList
            
    except Exception as exc:
        _LOGGER.error(f"Error getting devices from {address}: {exc}")
        raise


async def getDeviceInfoAsync(self, address, deviceId):
    _LOGGER.debug(f"Getting device info for {deviceId} from {address}")
    try:
        async with websockets.connect(
                f"ws://{address}/b_xmlproc/",
                extensions=[permessage_deflate.ClientPerMessageDeflateFactory()],
                origin=f'http://{address}',
                subprotocols=['b_xmlproc'],
                timeout=10  # Add timeout
            ) as websocket:

            getMnetDetailsPayload = getMnetDetails([deviceId])
            _LOGGER.debug(f"Sending device info request for {deviceId}")
            await websocket.send(getMnetDetailsPayload)
            mnetDetailsResultStr = await websocket.recv()
            _LOGGER.debug(f"Received device info response for {deviceId}: {mnetDetailsResultStr[:200]}...")
            
            mnetDetailsResultXML = ET.fromstring(mnetDetailsResultStr)

            result = {}
            node = mnetDetailsResultXML.find('./DatabaseManager/Mnet')

            await websocket.close()

            if node is not None:
                return node.attrib
            else:
                _LOGGER.warning(f"No device info found for device {deviceId}")
                return {}
                
    except Exception as exc:
        _LOGGER.error(f"Error getting device info for {deviceId} from {address}: {exc}")
        return {}


async def sendAsync(self, address, deviceId, attributes):
    _LOGGER.info(f"Sending command to device {deviceId} at {address}: {attributes}")
    try:
        async with websockets.connect(
                f"ws://{address}/b_xmlproc/",
                extensions=[permessage_deflate.ClientPerMessageDeflateFactory()],
                origin=f'http://{address}',
                subprotocols=['b_xmlproc'],
                timeout=10  # Add timeout
            ) as websocket:

            attrs = " ".join([f'{key}="{attributes[key]}"' for key in attributes])
            payload = f"""<?xml version="1.0" encoding="UTF-8" ?>
```

<Packet>
<Command>setRequest</Command>
<DatabaseManager>
<Mnet Group="{deviceId}" {attrs}  />
</DatabaseManager>
</Packet>
"""
                _LOGGER.debug(f"Sending payload: {payload}")
                await websocket.send(payload)

```
            # Wait for and read the response to check if command was accepted
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                _LOGGER.debug(f"Received response: {response}")
                
                # Parse response to check for errors
                try:
                    response_xml = ET.fromstring(response)
                    # Check if there's an error in the response
                    error = response_xml.find('.//Error')
                    if error is not None:
                        _LOGGER.error(f"Device returned error: {error.text}")
                        return False
                    else:
                        _LOGGER.info(f"Command sent successfully to device {deviceId}")
                        return True
                except ET.ParseError:
                    _LOGGER.warning(f"Could not parse response from device {deviceId}")
                    return True  # Assume success if we can't parse
                    
            except asyncio.TimeoutError:
                _LOGGER.warning(f"No response received from device {deviceId} within timeout")
                return True  # Assume success if no response (some devices don't respond)

            await websocket.close()
            return True
            
    except Exception as exc:
        _LOGGER.error(f"Error sending command to device {deviceId} at {address}: {exc}")
        return False
```