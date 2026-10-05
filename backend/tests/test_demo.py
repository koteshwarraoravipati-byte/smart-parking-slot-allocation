from app.demo import run_demo
def test_process_local_synchronization():
    result = run_demo(20, 3)
    assert result["peak_active"] <= 3
    assert result["mutex_counter"] == 20
    assert len(result["events"]) == 40
    assert result["events"][-1]["active"] == 0
