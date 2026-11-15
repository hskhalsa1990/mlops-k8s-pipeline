"""The rate limiter must not grow without bound as new clients appear."""
import predict


def test_idle_clients_are_pruned():
    predict._hits.clear()
    predict._hits["ip:stale"].append(0.0)
    predict._hits["ip:empty"]  # creates an empty window
    predict._hits["ip:active"].append(1000.0)

    predict._prune_idle_clients(now=1010.0)

    assert list(predict._hits) == ["ip:active"]
    predict._hits.clear()
