class StapelPresets:
    def __init__(self) -> None:
        self.color = ''
        
        self.stapel = {
            1: 'dp200;800;180', #
            2: 'dp200;700;0', #
            3: 'dp850;1350;0', #
            4: 'dp1150;1350;0', #
            5: 'dp2800;800;180', #
            6: 'dp2800;700;0', #
            7: 'dp2250;400;180', #
            8: 'dp750;400;180', #
            9: 'dp1100;540;0',
            10: 'dp900;540;0',
        }
        
        self.blue_stapel = {
            1: self.stapel[10], #10
        }
        
        self.yellow_stapel = {
            1: self.stapel[9], #9
        }
        
        self.blue_zones = {
            1: 'dp1750;500;180', #3
            2: 'dp30;04;30', #
            3: 'dp30;04;30', #
        }
        
        self.yellow_zones = {
            1: 'dp1250;500;180', #4
            2: 'dp30;04;30', #
            3: 'dp30;04;30', #
        }
        
    def get_stapel(self, stapel: int, zone: int):
        drive_stapel = self.blue_stapel[stapel] if self.color == 'blue' else self.yellow_stapel[stapel]
        drive_zone = self.blue_zones[zone] if self.color == 'blue' else self.yellow_zones[zone]
        
        return [drive_stapel, 'pg', 'dd200', 'gs', drive_zone, 'rs', 'ip12', 'dd-200', 'ge']
            