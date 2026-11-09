import unittest
from bridge_harness.core import Board, Game, symbol, SEATS
from prepare_episodes import extract, deal_identity


class EpisodeTest(unittest.TestCase):
    def episode(self):
        board=Board.from_dict(dict(id='test',hands=['AKQJT98765432...','.AKQJT98765432..','..AKQJT98765432.','...AKQJT98765432'],contract='3N',declarer='W'))
        game=Game(board); actions=[]
        for _ in range(16):
            c=game.observation().legal[0]
            actions.append(dict(seat=SEATS[game.actor],card=symbol(c)))
            game.play(c)
        return dict(status='ok',family='source',board=board.to_dict(),focal=dict(tables=[dict(status='ok',actions=actions)]))

    def test_replays_cards_and_keeps_related_positions_together(self):
        rows=extract(self.episode(),[4,8])
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[0]['family'],rows[1]['family'])
        for row,remaining in zip(rows,[48,44]):
            self.assertEqual(sum(x.bit_count() for x in row['key'][:16]),remaining)
            self.assertEqual(row['key'][24],remaining-4)
            self.assertEqual(row['key'][18],0)

    def test_deal_identity_ignores_contract_and_hand_permutation(self):
        d=self.episode()['board'];a=deal_identity(Board.from_dict(d))
        d['hands']=d['hands'][1:]+d['hands'][:1];d['contract']='4S';d['auction']=[]
        self.assertEqual(a,deal_identity(Board.from_dict(d)))

    def test_invalid_play_is_rejected(self):
        d=self.episode();d['focal']['tables'][0]['actions'][0]['card']='HA'
        with self.assertRaises(ValueError):extract(d,[4,8])

    def test_incomplete_and_failed_records_are_rejected(self):
        d=self.episode();d['status']='failed'
        with self.assertRaises(ValueError):extract(d,[4])
        d=self.episode();d['focal']['tables'][0]['actions']=[]
        with self.assertRaises(ValueError):extract(d,[4])


if __name__=='__main__':unittest.main()
