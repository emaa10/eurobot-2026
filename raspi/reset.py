from modules.motor_controller import MotorController
import asyncio


async def main():
    controller = MotorController()
    await controller.set_stop()
    
if __name__ == "__main__":
    asyncio.run(main())