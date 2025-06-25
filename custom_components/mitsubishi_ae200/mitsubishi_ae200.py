import logging
import asyncio
import websockets
from websockets.extensions import permessage_deflate
import xml.etree.ElementTree as ET

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
self._connection_timeout = 15
self._response_timeout = 10

```
async def _create_connection(self, address):
    """Create websocket connection with proper error handling."""
    try:
        websocket = await websockets.connect(
            f"ws://{address}/b_xmlproc/",
            extensions=[permessage_deflate.ClientPerMessageDeflateFactory()],
            origin=f'http://{address}',
            subprotocols=['b_xmlproc'],
            timeout=self._connection_timeout,
            ping_interval=None,  # Disable ping/pong
            ping_timeout=None,   # Disable ping timeout
            close_timeout=5      # Quick close timeout
        )
        return websocket
    except Exception as exc:
        _LOGGER.error(f"Failed to create websocket connection to {address}: {exc}")
        raise

async def getDevicesAsync(self, address):
    """Get list of devices from controller."""
    _LOGGER.info(f"Getting devices from {address}")
    websocket = None
    try:
        websocket = await self._create_connection(address)
        
        await websocket.send(getUnitsPayload)
        response = await asyncio.wait_for(websocket.recv(), timeout=self._response_timeout)
        
        unitsResultXML = ET.fromstring(response)
        groupList = []
        
        for r in unitsResultXML.findall('./DatabaseManager/ControlGroup/MnetList/MnetRecord'):
            device_id = r.get('Group')
            device_name = r.get('GroupNameWeb')
            if device_id and device_name:
                groupList.append({
                    "id": device_id,
                    "name": device_name
                })

        _LOGGER.info(f"Found {len(groupList)} devices at {address}")
        return groupList
        
    except Exception as exc:
        _LOGGER.error(f"Error getting devices from {address}: {exc}")
        raise
    finally:
        if websocket:
            try:
                await websocket.close()
            except:
                pass

async def getDeviceInfoAsync(self, address, deviceId):
    """Get detailed information for a specific device."""
    _LOGGER.debug(f"Getting device info for {deviceId} from {address}")
    websocket = None
    try:
        websocket = await self._create_connection(address)
        
        payload = getMnetDetails([deviceId])
        await websocket.send(payload)
        response = await asyncio.wait_for(websocket.recv(), timeout=self._response_timeout)
        
        responseXML = ET.fromstring(response)
        node = responseXML.find('./DatabaseManager/Mnet')
        
        if node is not None:
            return node.attrib
        else:
            _LOGGER.warning(f"No device info found for device {deviceId}")
            return {}
            
    except Exception as exc:
        _LOGGER.error(f"Error getting device info for {deviceId}: {exc}")
        return {}
    finally:
        if websocket:
            try:
                await websocket.close()
            except:
                pass

async def sendAsync(self, address, deviceId, attributes, verify=True):
    """Send command to device with optional verification."""
    _LOGGER.info(f"Sending command to device {deviceId}: {attributes}")
    websocket = None
    
    try:
        websocket = await self._create_connection(address)
        
        # Format attributes for XML
        attrs = " ".join([f'{key}="{str(attributes[key])}"' for key in attributes])
        payload = f"""<?xml version="1.0" encoding="UTF-8" ?>
```

<Packet>
<Command>setRequest</Command>
<DatabaseManager>
<Mnet Group="{deviceId}" {attrs} />
</DatabaseManager>
</Packet>
"""

```
        _LOGGER.debug(f"Sending payload to {deviceId}: {payload}")
        await websocket.send(payload)
        
        # Wait for response
        try:
            response = await asyncio.wait_for(websocket.recv(), timeout=self._response_timeout)
            _LOGGER.debug(f"Received response from {deviceId}: {response}")
            
            # Parse response for errors
            try:
                response_xml = ET.fromstring(response)
                error_node = response_xml.find('.//Error')
                if error_node is not None:
                    error_msg = error_node.text or "Unknown error"
                    _LOGGER.error(f"Device {deviceId} returned error: {error_msg}")
                    return False
                    
                # Check for success indicators
                success_node = response_xml.find('.//Success')
                if success_node is not None:
                    _LOGGER.info(f"Device {deviceId} confirmed command success")
                    return True
                    
                # If no explicit error or success, assume success
                _LOGGER.info(f"Command sent to device {deviceId}, no error response")
                return True
                
            except ET.ParseError as parse_exc:
                _LOGGER.warning(f"Could not parse response from device {deviceId}: {parse_exc}")
                return True  # Assume success if we can't parse but got a response
                
        except asyncio.TimeoutError:
            _LOGGER.warning(f"No response from device {deviceId} within {self._response_timeout}s")
            return True  # Some devices don't respond to set commands
            
    except Exception as exc:
        _LOGGER.error(f"Error sending command to device {deviceId}: {exc}")
        return False
    finally:
        if websocket:
            try:
                await websocket.close()
            except:
                pass

async def sendAndVerifyAsync(self, address, deviceId, attributes, max_retries=3):
    """Send command and verify it was applied by reading back the values."""
    _LOGGER.info(f"Sending and verifying command to device {deviceId}: {attributes}")
    
    for attempt in range(max_retries):
        try:
            # Send the command
            success = await self.sendAsync(address, deviceId, attributes)
            if not success:
                _LOGGER.warning(f"Command failed on attempt {attempt + 1} for device {deviceId}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)  # Wait before retry
                    continue
                return False
            
            # Wait for device to process
            await asyncio.sleep(2)
            
            # Verify by reading back the device state
            device_info = await self.getDeviceInfoAsync(address, deviceId)
            if not device_info:
                _LOGGER.warning(f"Could not read device state for verification on attempt {attempt + 1}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
                    continue
                return False
            
            # Check if our values were applied
            verification_failed = False
            for key, expected_value in attributes.items():
                actual_value = device_info.get(key)
                
                # Convert to string for comparison
                expected_str = str(expected_value)
                actual_str = str(actual_value) if actual_value is not None else None
                
                # For temperature values, allow small differences due to rounding
                if key in ["SetTemp", "SetTemp1", "SetTemp2"] and actual_str and expected_str:
                    try:
                        expected_float = float(expected_str)
                        actual_float = float(actual_str)
                        if abs(expected_float - actual_float) <= 0.5:
                            _LOGGER.debug(f"Temperature {key} verified: {actual_float}°C (expected {expected_float}°C)")
                            continue
                    except ValueError:
                        pass
                
                # For other values, exact match
                if actual_str == expected_str:
                    _LOGGER.debug(f"Value {key} verified: {actual_str}")
                    continue
                else:
                    _LOGGER.warning(f"Verification failed for {key}: expected '{expected_str}', got '{actual_str}'")
                    verification_failed = True
                    break
            
            if not verification_failed:
                _LOGGER.info(f"Command successfully verified for device {deviceId}")
                return True
            else:
                _LOGGER.warning(f"Verification failed on attempt {attempt + 1} for device {deviceId}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2)  # Wait longer before retry
                    continue
                return False
                
        except Exception as exc:
            _LOGGER.error(f"Error during send and verify attempt {attempt + 1} for device {deviceId}: {exc}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2)
                continue
            return False
    
    return False
```