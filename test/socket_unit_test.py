import json
import unittest

from DataConverter import DataConverter


class MyTestCase(unittest.TestCase):
    # 받는 액션 형식
    dum1 = {"player_id": 1, "player_turn": 0, "player_action": 2}
    # 받는 데이터 형식
    dum2 = {"player_turn": 2,
            "all_players_data": [{"player_id": 1, "cardDeckOnTable_volume": 2, "cardDeckOnTable_type": 3},
                                 {"player_id": 2, "cardDeckOnTable_volume": 2, "cardDeckOnTable_type": 3},
                                 {"player_id": 3, "cardDeckOnTable_volume": 2, "cardDeckOnTable_type": 3}]}
    # 보내는 액션 형식
    dum3 = {"player_id": 1, "player_action": 12}

    def test_something(self):
        DataConverter(self.receive_action_test())

    def test_convert(self):

        data = DataConverter(bytes(int.from_bytes(self.receive_action_test(), 'little').to_bytes(1024, 'little')))

        data.send({value: key for key, value in DataConverter.player_action.items()}[12])

        self.assertEqual(data.my_action, data.player_action["PLAYER_NOT_WANT"])

        data.recv(bytes(int.from_bytes(self.receive_data_test(), 'little').to_bytes(1024, 'little')))

        self.assertEqual(data.player_turn, 2)

        self.assertEqual(data.get_player_by_id(1), {'player_id': 1, 'card': {'type': 'PLUM', 'volume': 3}})

        self.assertEqual(data.get_card_by_id(1), data.get_card_my())

    def test_recv(self):
        data = DataConverter(bytes(int.from_bytes(self.receive_action_test(), 'little').to_bytes(1024, 'little')))
        data.recv(bytes(int.from_bytes(self.receive_data_test(), 'little').to_bytes(1024, 'little')))
        # self.assertEqual(data.player_turn, 2)
        self.assertEqual(str(data), str(self.dum2))
        self.assertEqual(data.get_player_by_id(1), {'player_id': 1, 'card': {'type': 'PLUM', 'volume': 5}})
        self.assertEqual(data.get_card_by_id(1), data.get_card_my())


    def test_send(self):
        data = DataConverter(bytes(int.from_bytes(self.receive_action_test(), 'little').to_bytes(1024, 'little')))
        data.send({value: key for key, value in DataConverter.player_action.items()}[12])
        self.assertEqual(data.my_action, data.player_action["PLAYER_NOT_WANT"])


    def receive_action_test(self):
        return json.dumps(self.dum1).encode('utf-8')

    def receive_data_test(self):
        return json.dumps(self.dum2).encode('utf-8')

    def send_action_test(self):
        dum3 = self.dum1['player_action'] = 12
        return json.dumps(dum3).encode('utf-8')



if __name__ == '__main__':
    unittest.main()
