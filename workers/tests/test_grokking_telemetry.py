import torch

from pokelab_workers.kits.grokking.telemetry import embed_fourier_concentration, embed_norm


class _FakeEmbedModel(torch.nn.Module):
    def __init__(self, p, d=16):
        super().__init__()
        self.embed = torch.nn.Embedding(p + 1, d)


def test_embed_norm_is_a_real_l2_norm():
    torch.manual_seed(0)
    model = _FakeEmbedModel(p=50)
    expected = model.embed.weight.detach().norm().item()
    assert abs(embed_norm(model) - expected) < 1e-5


def test_fourier_concentration_distinguishes_random_from_periodic():
    torch.manual_seed(0)
    p = 113  # the real grokking config's p

    random_model = _FakeEmbedModel(p)
    random_concentration = embed_fourier_concentration(random_model, p)

    periodic_model = _FakeEmbedModel(p)
    with torch.no_grad():
        t = torch.arange(p).float().unsqueeze(1)
        base = torch.cat([torch.sin(2 * 3.14159 * 2.0 * t / p), torch.cos(2 * 3.14159 * 2.0 * t / p)], dim=1)
        periodic_model.embed.weight[:p] = base.repeat(1, 8)[:, :16]
    periodic_concentration = embed_fourier_concentration(periodic_model, p)

    assert periodic_concentration > random_concentration
    assert periodic_concentration > 0.9
    assert random_concentration < 0.5


def test_concentration_is_bounded_in_0_1():
    model = _FakeEmbedModel(p=20)
    c = embed_fourier_concentration(model, 20)
    assert 0.0 <= c <= 1.0
