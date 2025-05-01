'''This example shows how time can be synchronized across multiple
moteus controllers.  When time is synchronized in this way, then
trajectory commands that would take the same amount of time will
complete simultaneously.'''

import argparse
import asyncio
import math
import moteus
import time
import logging

from modules.drive_state import DriveState
from modules.arduino_com import Arduino
from modules.lidar import Lidar
from modules.pathfinding import Pathfinder
from modules.position import Position

LIDAR = True

class ServoClock:
    '''This class can be used to keep a controller's time base
    synchronized with the host time base.

    Instantiate it, then call await ServoClock.update_second() at a
    regular rate, approximately at 1Hz.
    '''

    # This constant should be approximately 5-10x the update rate.
    # Smaller means that the device time will converge with the host
    # time more quickly, but will also be less stable.
    TIME_CONSTANT = 5.0

    # This is the approximate change in clock rate of the device for
    # each trim count change.
    TRIM_STEP_SIZE = 0.0025

    def __init__(self, controller, measure_only=False):
        self.controller = controller
        self.initial_time = None
        self.state = None
        self.device_ms_count = 0
        self.measure_only = measure_only

        # This is the currently reported time error between the host
        # and the device.
        self.time_error_s = 0.0

        self._query = self.controller.make_custom_query(
            {moteus.Register.MILLISECOND_COUNTER : moteus.INT32,
             moteus.Register.CLOCK_TRIM: moteus.INT32}
        )
        
    def _calculate_ms_delta(self, time1, time2):
        # These are returned as int32s, so they may have wrapped around.
        if time2 < 0 and time1 > 0:
            result_ms = time2 + (2**32) - time1
        else:
            result_ms = time2 - time1
        if result_ms > 100000 or time2 < time1:
            # We'll assume any difference of more than 100s is a problem
            # (or a negative difference).
            return None
        return result_ms

    async def update_second(self):
        '''This should be called at a regular interval, no more often than
        once per second.
        '''

        old_state = self.state

        self.state = await self.controller.execute(self._query)

        now = time.time()

        ms_count_delta = 0

        if old_state is not None:
            ms_count_delta = self._calculate_ms_delta(
                old_state.values[moteus.Register.MILLISECOND_COUNTER],
                self.state.values[moteus.Register.MILLISECOND_COUNTER])

            if ms_count_delta is None:
                # We became desynchronized and need to restart.
                self.device_ms_count = 0
                self.initial_time = None
            else:
                self.device_ms_count += ms_count_delta

        if self.initial_time is not None and ms_count_delta != 0:
            # We have enough information to calculate an update.

            # First, we calculate the delta between our starting time
            # and now in the host timespace.
            total_host_time = now - self.initial_time

            # And the amount of host time that has advanced since our
            # last call.  This should be approximately 1s.
            period_host_time = now - self.last_time

            # Now measure the absolute drift in seconds between the
            # device and our host clock.
            absolute_drift = self.device_ms_count / 1000 - total_host_time
            self.time_error_s = absolute_drift

            # And secondarily measure the ratio between the device
            # time and host time during the last period.
            rate_drift = (ms_count_delta / 1000) / period_host_time

            # What drift would we need to cancel out our total
            # absolute drift over the next TIME_CONSTANT seconds?
            desired_drift = 1 + -absolute_drift / self.TIME_CONSTANT

            # Figure out how much we need to change the devices clock
            # rate in order to cancel that drift, both as a floating
            # point value, then again in integer counts.
            delta_drift = desired_drift - rate_drift
            delta_drift_integral = round(delta_drift / self.TRIM_STEP_SIZE)

            # Finally, we figure out the new trim value we should ask
            # for.
            new_trim = (self.state.values[moteus.Register.CLOCK_TRIM] +
                        delta_drift_integral)

            if not self.measure_only:
                await self.controller.set_trim(trim=new_trim)

        if self.initial_time is None:
            self.initial_time = now

        self.last_time = now


class Poller:
    TIMESTAMP_S = 0.01
    CLOCK_UPDATE_S = 1.0

    def __init__(self, controllers: dict[int, moteus.Controller], args: argparse.ArgumentParser):
        self.controllers = controllers
        self.last_time = time.time()
        self.servo_data = {x.id: {}
                               for x in self.controllers.values()}
        self.servo_clocks = {
            x.id: ServoClock(x, measure_only=args.no_synchronize)
            for x in controllers.values()
        }

        self.next_clock_time = self.last_time + self.CLOCK_UPDATE_S
        

    async def wait_for_event(self, condition, timeout=None, per_cycle=None):
        start = time.time()
        while True:
            now = time.time()
            if (now - start) > timeout:
                raise RuntimeError("timeout")

            if now > self.next_clock_time:
                self.next_clock_time += self.CLOCK_UPDATE_S
                [await x.update_second() for x in self.servo_clocks.values()]

            self.last_time += self.TIMESTAMP_S
            delta_s = self.last_time - now
            await asyncio.sleep(delta_s)

            self.servo_data = {x.id : await x.query()
                               for x in self.controllers.values()}

            if per_cycle:
                per_cycle()

            if condition():
                return

class MotorController():
    def __init__(self) -> None:
        parser = argparse.ArgumentParser()
        parser.add_argument('--no-synchronize', action='store_true')
        parser.add_argument('--verbose', '-v', action='store_true')

        args = parser.parse_args()

        self.SERVO_IDS = [1, 2]

        qr = moteus.QueryResolution()
        qr.trajectory_complete = moteus.INT8
        qr.fault = moteus.INT8 

        self.controllers = {x: moteus.Controller(x, query_resolution=qr) for x in self.SERVO_IDS}

        self.poller = Poller(self.controllers, args)
        
        self.serial_manager = Arduino()
        self.lidar = Lidar() if LIDAR else None
            
        if LIDAR and not self.lidar.start_scanning():
            self.logger.info("Failed to start Lidar")
            return
        
        self.logger = logging.getLogger(__name__)
        
        self.x = 0
        self.y = 0
        self.theta = 0.0
                
        self.target_positions = {1: 0, 2: 0}
        
        self.finished = False
        self.stopped = False
        self.stopped_since = None
        self.need_to_continue = False
        self.stop = False
        self.direction = 0
        self.abortable = True
        
        
    def set_pos(self, x, y, theta):
        self.x = x
        self.y = y
        self.theta = theta
        
        self.serial_manager.set_pos(self.x, self.y, self.theta)
        
    async def get_pos(self):
        servo_data = {x.id: await x.query() for x in self.controllers.values()}
                        
        return [data.values[moteus.Register.POSITION] for data in servo_data.values()]
    
        
    async def get_finished(self) -> bool:
        servo_data = {x.id: await x.query() for x in self.controllers.values()}
                        
        return all(data.values[moteus.Register.TRAJECTORY_COMPLETE] for data in servo_data.values())
    
    async def get_torque(self):
        servo_data = {x.id: await x.query() for x in self.controllers.values()}
        
        torque = max(data.values[moteus.Register.TORQUE] for data in servo_data.values())
            
        return torque
    
    async def get_velocity(self):
        servo_data = {x.id: await x.query() for x in self.controllers.values()}
        
        velocity = min(abs(data.values[moteus.Register.VELOCITY]) for data in servo_data.values())
            
        return velocity
    
    async def set_stop(self):
        for motor_id, controller in self.controllers.items():
            await controller.set_position(
                position=math.nan, 
                velocity_limit=0, 
            )
        
        [await controller.set_stop() for controller in self.controllers.values()]

    async def override_target(self):
        servo_data = {x.id: await x.query() for x in self.controllers.values()}
        
        for i, data in enumerate(servo_data.values()):
            self.target_positions[i+1] = self.target_positions[i+1] - data.values[moteus.Register.POSITION]
    
    async def set_target(self, velocity_limit=60.0, accel_limit=20.0, maximum_torque=0.05) -> None:
        # Set zero position
        [await controller.set_output_exact(position=0.0)
        for motor_id, controller in self.controllers.items()]
        
        for motor_id, controller in self.controllers.items():
            await controller.set_position(
                position=self.target_positions.get(motor_id, 0), 
                velocity_limit=velocity_limit, 
                accel_limit=accel_limit, 
                maximum_torque=maximum_torque,
                watchdog_timeout=math.nan,
            )
            
    async def drive_to_target(self, pos1: int, pos2: int, velocity_limit=60.0, accel_limit=20.0, maximum_torque=0.05) -> None:
        self.target_positions = {1: pos1, 2: -pos2}
        await self.set_target(velocity_limit, accel_limit, maximum_torque)
        
        
    async def drive_distance(self, dist:int) -> None:
        self.direction = 1 if dist > 0 else -1
        self.finished = False
        
        pulses_per_mm = 0.067
        pulses = dist * pulses_per_mm
        
        await self.drive_to_target(pulses, pulses)
        
        while not self.finished:
            self.control_loop()
        
    async def turn_angle(self, angle: float) -> None:
        self.direction = 0
        self.finished = False
        
        turn = 11.7
        pulses_per_degree=turn/90
        pulses = angle*pulses_per_degree
                
        await self.drive_to_target(-pulses, pulses, velocity_limit=35.0, accel_limit=14.0)
        
        target_theta = self.theta + angle
        if target_theta < 0: target_theta += 360
        if target_theta > 360: target_theta -= 360
        
        while not self.finished:
            self.control_loop()
            
            if abs(self.theta - target_theta) < angle//80:
                break
        
        await self.set_stop()  
        
    async def turn_to(self, theta: float):
        delta_t = theta - self.theta
        while (delta_t > 180): delta_t -= 360
        while (delta_t < -180): delta_t += 360
        
        await self.turn_angle(delta_t)
    
    async def drive_to(self, x: int, y: int):
        delta_x = x - self.x
        delta_y = y - self.y
                
        dist = math.sqrt(delta_x**2+delta_y**2)
                
        delta_t = (delta_x/dist) - self.theta * math.pi / 180
                
        # normalize theta
        while (delta_t > math.pi): delta_t -= 2 * math.pi
        while (delta_t < -math.pi): delta_t += 2 * math.pi
        
        delta_t *= 180 / math.pi
        
        await self.turn_angle(delta_t)
        await self.drive_distance(dist)
    
    async def drive_to_point(self, x, y, theta):
        points = self.pathfinder.proccess(start=Position(self.x//10, self.y//10), target=Position(int(x)//10, int(y)//10))
        for point in points:
            await self.drive_to(point.x*10, point.y*10)
        
        await self.turn_to(theta)
        
    async def clean_wheels(self) -> None:
        for motor_id, controller in self.controllers.items():
            await controller.set_position(
                position=math.nan, 
                velocity_limit=10, 
                accel_limit=50, 
                watchdog_timeout=math.nan
            )
        
        
    async def home(self):
        [await controller.set_output_exact(position=0.0)
        for motor_id, controller in self.controllers.items()]
        
        await self.drive_to_target(-999, -999, 5, 50, 0.05)
        
        accellerated = False
        
        while True:
            torque = await self.get_torque()
            velocity = await self.get_velocity()
            if velocity > 4.9: accellerated = True
            if accellerated and torque > 0.049 and velocity < 0.1: break
        
        await self.set_stop()
        
    async def control_loop(self):
        self.finished = await self.get_finished()
                            
        if self.finished:
            await self.set_stop()
            
        try:
            self.x, self.y, self.theta = self.serial_manager.get_pos()
        except:
            self.logger.info("Could not read new pos data")
            
        # lidar
        if LIDAR:
            latest_scan = self.lidar.get_latest_scan()
            stop = False
            
            for angle, distance in latest_scan:
                # point in relation to bot
                d_x = distance * math.sin(angle * math.pi / 180)
                d_y = distance * math.cos(angle * math.pi / 180)
                
                # point in arena
                arena_angle = (-angle) + self.theta
                arena_x = distance * math.cos(arena_angle * math.pi / 180) + self.x
                arena_y = distance * math.sin(arena_angle * math.pi / 180) + self.y
                
                point_in_arena = 100 <= arena_x <= 2900 and 100 <= arena_y <= 190    # 5cm threshold
                point_in_arena = True
                            
                if (self.direction >= 0 and 0 <= d_y <= 500) and abs(d_x) <= 250 and point_in_arena:
                    stop = True
                    self.logger.info(f'Obstacle: x: {d_x}, y: {d_y}, angle: {angle}, distance: {distance}')
                    break
                
                if  (self.direction <= 0 and 0 >= d_y >= -500) and abs(d_x) <= 250 and point_in_arena:
                    stop = True
                    self.logger.info(f'Obstacle: x: {d_x}, y: {d_y}, angle: {angle}, distance: {distance}')
                    break
                
            self.stop = stop
        
        if self.stopped and not self.stopped_since: self.stopped_since = time()
        if not self.stopped and self.stopped_since: self.stopped_since = None
        
        if self.stop:
            self.finished = False
            if not self.stopped:
                await self.override_target()
                await self.stop()
                self.stopped = True
                self.need_to_continue = True
        
        if self.need_to_continue and not self.stop:
            await self.set_target()
            self.need_to_continue = False
            self.stopped = False
            
        if self.time_started + 90 < time():
            pass    # drive home
            
        if self.time_started + 99 < time():
            self.logger.info('Cutoff')
            await self.set_stop()
            self.finished = True
        
        if LIDAR and not self.lidar.is_running():
            self.logger.info("Lidar thread stopped unexpectedly")
            LIDAR = False