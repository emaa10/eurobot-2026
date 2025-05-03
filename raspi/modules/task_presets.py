class TaskPresets:
    def __init__(self) -> None:
        self.color = ''
        
        self.stapel = {
            1: 'dp200;800;180',
            2: 'dp200;700;0',
            3: 'dp850;1350;0',
            4: 'dp1150;1350;0',
            5: 'dp2800;800;180',
            6: 'dp2800;700;0',
            7: 'dp2250;400;180',
            8: 'dp750;400;180',
            9: 'dp1100;600;0',
            10: 'dp900;600;0',
        }
        
        self.blue_zones = {
            1: 'dp30;04;30', #
            2: 'dp30;04;30', #
            3: 'dp30;04;30', #
        }
        
        self.yellow_zones = {
            1: 'dp30;04;30', #
            2: 'dp30;04;30', #
            3: 'dp30;04;30', #
        }
    def stapel(self, stapel: int, zone: int):
        drive_stapel = self.stapel[stapel]
        drive_zone = self.blue_zones[zone] if self.color == 'blue' else self.yellow_zones[zone]
        
        return [drive_stapel, 'dd300', 'gs', drive_zone, 'ga']
        
    def flag(self):
        x = 300 if self.color == 'blue' else 1700
        return [f'hh'] #gf fehlt
            