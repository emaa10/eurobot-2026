class StapelPresets:
    def __init__(self) -> None:
        self.color = ''
        
        self.stapel = {
            1: 'dp200;800;180', #
            2: 'dp400;1360;270', 
            3: 'dp850;1500;0',
            4: 'dp1150;1350;0', #
            5: 'dp2700;1325;90', 
            6: 'dp2800;700;0', #
            7: 'dp2250;400;180', #
            8: 'dp750;400;180', #
            9: 'dp1100;540;0',
            10: 'dp900;540;0',
        }
        
        self.blue_stapel = {
            1: self.stapel[10], #10
            2: self.stapel[2]
        }
        
        self.yellow_stapel = {
            1: self.stapel[9], #9
            2: self.stapel[2],
            3: self.stapel[3],
        }
        
        self.blue_zones = {
            1: 'dp1750;500;180', #5
            2: 'dp30;04;30', #
            3: 'dp30;04;30', #
        }
        
        self.yellow_zones = {
            1: 'dp1250;500;0', #2
            2: 'dp400;1720;0', # 3
            3: 'dp30;04;30', #
        }
        
    def get_stapel(self, stapel: int, zone: int, flagge = False):
        drive_stapel = self.blue_stapel[stapel] if self.color == 'blue' else self.yellow_stapel[stapel]
        drive_zone = self.blue_zones[zone] if self.color == 'blue' else self.yellow_zones[zone]
        
        if flagge:
            return [drive_stapel, 'dd20', 'gs', 'dd-100', drive_zone, 'hh', 'fd', 'ip20', 'ds', 'ip12', 'dd-200', 'ge']
            
        return [drive_stapel, 'pg', 'dd120', 'gs', 'dd-100', drive_zone, 'ds', 'ip12', 'dd-200', 'ge']
        
        
            