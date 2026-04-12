
import asyncio
import logging
import json
from pathlib import Path
from roborock.cli import RoborockContext, DeviceConnectionManager
from roborock.roborock_typing import RoborockCommand
from roborock.map.map_parser import MapParser, MapParserConfig

# Configure logging
logging.basicConfig(level=logging.INFO)
_LOGGER = logging.getLogger(__name__)

async def explore_map_data(duid: str):
    context = RoborockContext()
    context.validate()
    
    conn_manager = DeviceConnectionManager(context)
    try:
        device = await conn_manager.get_device(duid)
        _LOGGER.info(f"Connected to device: {device.duid}")
        
        # Pull map binary using the trait
        _LOGGER.info("Fetching map data via MapContentTrait...")
        map_trait = device.v1_properties.map_content
        await map_trait.refresh()
        
        map_data = map_trait.map_data
        if not map_data:
            _LOGGER.error("Failed to parse map data")
            return
            
        # Save image for visual verification
        if map_trait.image_content:
            image_path = Path("explore_map.png")
            image_path.write_bytes(map_trait.image_content)
            _LOGGER.info(f"Saved map image to {image_path}")

        _LOGGER.info("--- MapData Inspection ---")
        _LOGGER.info(f"Image exists: {map_data.image is not None}")
        if map_data.image:
            img = map_data.image
            _LOGGER.info(f"Image Object: {type(img)}")
            # Enumerate all attributes of ImageData
            for attr in dir(img):
                if not attr.startswith('_'):
                    val = getattr(img, attr)
                    if not callable(val):
                        _LOGGER.info(f"  ImageData Attribute '{attr}': {type(val)}")
                        if attr == 'data':
                            _LOGGER.info(f"    Image Size: {val.size}")
                        else:
                            _LOGGER.info(f"    Value: {val}")
        
        _LOGGER.info(f"Charger position: {map_data.charger}")
        _LOGGER.info(f"Vacuum position: {map_data.vacuum_position}")
        
        if map_data.rooms:
            _LOGGER.info(f"Found {len(map_data.rooms)} rooms")
            for room_id, room in map_data.rooms.items():
                _LOGGER.info(f"Room {room_id}: {room}")
        
        if map_data.walls:
            _LOGGER.info(f"Found {len(map_data.walls)} virtual walls")
            for wall in map_data.walls:
                _LOGGER.info(f"Wall: {wall}")
                
        if map_data.no_go_areas:
            _LOGGER.info(f"Found {len(map_data.no_go_areas)} no-go areas")
            for area in map_data.no_go_areas:
                _LOGGER.info(f"No-Go Area: {area}")

        # Check for raw blocks if available (to see if we can get more math)
        _LOGGER.info("--- Internal Structure Check ---")
        for attr in dir(map_data):
            if not attr.startswith('_'):
                val = getattr(map_data, attr)
                if not callable(val):
                    _LOGGER.info(f"Attribute '{attr}': {type(val)}")
                    # If it's a dict or list, show first few items
                    if isinstance(val, (dict, list)) and len(val) > 0:
                        _LOGGER.info(f"  Sample: {str(val)[:200]}...")

    finally:
        await conn_manager.close()

if __name__ == "__main__":
    TARGET_DUID = "7FjpPFODrdwoiHnJvL6eW2"
    asyncio.run(explore_map_data(TARGET_DUID))
