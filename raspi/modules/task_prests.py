from modules.task import Task

class TaskPresets:
    def __init__(self) -> None:
        self.presets = {
            'flag': ['dp500;200;0', 'hh', 'gf'],
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
        
    def get_flag_action_set(self, color: chr):
        return ['dp500;200;0', 'hh', 'gf']
            