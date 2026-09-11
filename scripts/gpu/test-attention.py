import unittest
import torch
from mmcv.cnn.bricks.transformer import MultiheadAttention
from research_adapter import enable_memory_efficient_attention

class AttentionTest(unittest.TestCase):
    def test_output_masks_and_checkpoint_are_preserved(self):
        torch.manual_seed(42)
        model = torch.nn.ModuleDict({'wrapped': MultiheadAttention(64, 4, batch_first=True), 'ordinary': torch.nn.MultiheadAttention(64, 4) }).eval()
        x = torch.randn(2, 19, 64)
        padding = torch.zeros(2, 19, dtype=torch.bool)
        padding[0, -2:] = True
        mask = torch.zeros(19, 19, dtype=torch.bool)
        mask[0, -1] = True
        state = {k: v.clone() for k, v in model.state_dict().items()}
        with torch.inference_mode():
            reference = model['wrapped'](x, x, x, key_padding_mask=padding, attn_mask=mask)
        self.assertEqual(enable_memory_efficient_attention(model), 1)
        self.assertEqual(enable_memory_efficient_attention(model), 0)
        with torch.inference_mode():
            actual = model['wrapped'](x, x, x, key_padding_mask=padding, attn_mask=mask)
        torch.testing.assert_close(actual, reference, rtol=1e-5, atol=1e-6)
        self.assertEqual(state.keys(), model.state_dict().keys())
        for key, value in model.state_dict().items():
            self.assertTrue(torch.equal(state[key], value), key)
        self.assertIsNone(model['wrapped'].attn(x.transpose(0,1), x.transpose(0,1), x.transpose(0,1))[1])
        self.assertIsNotNone(model['ordinary'](x.transpose(0,1), x.transpose(0,1), x.transpose(0,1))[1])

if __name__ == '__main__': unittest.main()
