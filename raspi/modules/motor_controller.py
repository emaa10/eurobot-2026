'''This example shows how time can be synchronized across multiple
moteus controllers.  When time is synchronized in this way, then
trajectory commands that would take the same amount of time will
complete simultaneously.'''

import argparse
import asyncio
import math
import moteus
import time


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
        
    def _calculate_ms_delta(time1, time2):
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

class Motorcontroller():
    def __init__(self) -> None:
        parser = argparse.ArgumentParser()
        parser.add_argument('--no-synchronize', action='store_true')
        parser.add_argument('--verbose', '-v', action='store_true')

        args = parser.parse_args()

        self.SERVO_IDS = [1, 2]

        qr = moteus.QueryResolution()
        qr.trajectory_complete = moteus.INT8

        self.controllers = {x: moteus.Controller(x, query_resolution=qr) for x in self.SERVO_IDS}

        self.poller = Poller(self.controllers, args)
    
    async def set_pos(self, pos1: int, pos2: int):
        [await controller.set_output_exact(position=0.0)
        for motor_id, controller in self.controllers.items()]
        
        target_positions = {1: -pos1, 2: pos2}  # forwards
        
        # Define velocity and acceleration limits
        velocity_limit = 25.0
        accel_limit = 20.0
        watchdog_timeout = math.nan  # No timeout for watchdog

        [await controller.set_position(position=target_positions.get(motor_id, 0), 
                                    velocity_limit=velocity_limit, 
                                    accel_limit=accel_limit, 
                                    watchdog_timeout=watchdog_timeout)
        for motor_id, controller in self.controllers.items()]

        await self.poller.wait_for_event(
            lambda: all([x.values[moteus.Register.TRAJECTORY_COMPLETE]
                        for x in self.poller.servo_data.values()]),
            timeout=120.0
        )
        
        time.sleep(0.5)
        
    async def drive(self, dist:int):
        await self.set_pos(dist, dist)
        
    async def turn(self, angle:int):
        turn = 14.25
        pulses_per_degree=turn/90
        pulses = angle*pulses_per_degree
        
        print(pulses)
        
        await self.set_pos(-pulses, pulses)
        

        
async def main():
    controller = Motorcontroller()
    
    async def test_case1():
        controller.drive(30)
        controller.drive(-30)
    
    async def test_case2():
        controller.drive(30)
        controller.drive(-30)
        
    async def test_case3():
        controller.drive(30)
        controller.drive(-30)
        
    async def test_case4():
        controller.drive(30)
        controller.drive(-30)
    


if __name__ == '__main__':
    asyncio.run(main())