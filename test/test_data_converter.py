import json
import unittest

from DataConverter import BUFFER_SIZE, DataConverter


class DataConverterTest(unittest.TestCase):
    action_payload = {"player_id": 1, "player_turn": 0, "player_action": 2}
    state_payload = {
        "game_status": 2,
        "player_turn": 2,
        "player_turn_index": 2,
        "winner_id": 0,
        "winner_index": 0,
        "active_player_count": 3,
        "all_players_data": [
            {
                "player_id": 1,
                "player_index": 1,
                "player_status": 4,
                "hand_count": 17,
                "table_count": 1,
                "total_count": 18,
                "score": 18,
                "cardDeckOnTable_volume": 2,
                "cardDeckOnTable_type": 3,
            },
            {
                "player_id": 2,
                "player_index": 2,
                "player_status": 4,
                "hand_count": 18,
                "table_count": 1,
                "total_count": 19,
                "score": 19,
                "cardDeckOnTable_volume": 2,
                "cardDeckOnTable_type": 3,
            },
            {
                "player_id": 3,
                "player_index": 3,
                "player_status": 4,
                "hand_count": 18,
                "table_count": 1,
                "total_count": 19,
                "score": 19,
                "cardDeckOnTable_volume": 2,
                "cardDeckOnTable_type": 3,
            },
        ],
    }

    def test_action_packet_loads(self):
        data = DataConverter(self.packet(self.action_payload))

        self.assertEqual(data.my_id, 1)
        self.assertEqual(data.my_action, data.player_action["PLAYER_READY"])

    def test_send_packet_updates_action_and_uses_protocol_size(self):
        data = DataConverter(self.packet(self.action_payload))
        payload = data.send("PLAYER_NOT_WANT")

        self.assertEqual(data.my_action, data.player_action["PLAYER_NOT_WANT"])
        self.assertEqual(len(payload), BUFFER_SIZE)

    def test_state_packet_updates_player_state(self):
        data = DataConverter(self.packet(self.action_payload))
        data.recv(self.packet(self.state_payload))

        self.assertEqual(data.player_turn, 2)
        self.assertEqual(data.get_turn_index(), 2)
        self.assertEqual(data.active_player_count, 3)
        self.assertEqual(data.get_player_by_id(1)["card"], {"type": "ORANGE", "volume": 2})
        self.assertEqual(data.get_player_by_id(1)["hand_count"], 17)
        self.assertEqual(data.get_player_by_id(1)["score"], 18)
        self.assertEqual(data.get_my_score(), 18)
        self.assertEqual(data.get_my_player()["player_index"], 1)
        self.assertEqual(data.get_card_by_id(1), data.get_card_my())
        self.assertEqual(str(data), json.dumps(self.state_payload))

    @staticmethod
    def packet(payload):
        return json.dumps(payload).encode("utf-8").ljust(BUFFER_SIZE, b"\0")


if __name__ == "__main__":
    unittest.main()
