from modules.task import Task

class TaskPresets:
    def __init__(self) -> None:
        self.stapel = {
            1: 'dp30;04;30',
            2: 'dp30;04;30',
            3: 'dp30;04;30',
            4: 'dp30;04;30',
            5: 'dp30;04;30',
            6: 'dp30;04;30',
            7: 'dp30;04;30',
            8: 'dp30;04;30',
            9: 'dp30;04;30',
        }
        
        self.blue_zones = {
            1: 'dp30;04;30',
            2: 'dp30;04;30',
            3: 'dp30;04;30',
        }
        
        self.yellow_zones = {
            1: 'dp30;04;30',
            2: 'dp30;04;30',
            3: 'dp30;04;30',
        }
    def get_stapel_action_set(self, preset: str, zone: int, color: bool):
        if not zone:
            return self.presets[preset]
        
        if color:
            return self.presets[preset].append(self.blue_zones[zone])
        else:
            return self.presets[preset].append(self.yellow_zones[zone])
        
    def get_flag_action_set(self, color: str):
        x = 500 if color == 'blue' else 1500
        return [f'dp{x};200;0', 'hh', 'gf']
            