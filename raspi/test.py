from data import SerialManager
import unittest

class TestBotMethods(unittest.TestCase):
    def test_regex(self):
        serial_obj = SerialManager()

        input_str = "l-23r25x23.3y-12.3t78.4"
        
        pos = serial_obj.extract_values(input_str)
        pos_actual = (-23, 25, 23, -12, 78.4)
        
        self.assertEqual(pos, pos_actual)
        
if __name__ == '__main__':
    unittest.main()