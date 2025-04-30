class TaskPresets:
    def __init__(self) -> None:
        self.stapel = {
            1: 'dp200;800;180',
            2: 'dp200;700;0',
            3: 'dp850;1350;0',
            4: 'dp1150;1350;0',
            5: 'dp2800;800;180',
            6: 'dp2800;700;0',
            7: 'dp2250;400;180',
            8: 'dp750;400;180',
            9: 'dp1100;600;0',#
            10: 'dp30;600;30',#
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
            