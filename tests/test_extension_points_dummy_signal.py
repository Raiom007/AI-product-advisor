
def test_register_dummy_signal(monkeypatch):
    from advisor.core.registries import ranking_signal
    from advisor.ranking.scorer import score_product
    from advisor.core.config import load_config
    
    # We will monkeypatch load_config so that it includes our dummy signal
    original_load = load_config
    def mock_load_config():
        cfg = original_load()
        if "ranking" not in cfg:
            cfg["ranking"] = {"weights": {}}
        elif "weights" not in cfg["ranking"]:
            cfg["ranking"]["weights"] = {}
            
        cfg["ranking"]["weights"]["_dummy_signal"] = 0.5
        cfg["ranking"]["weights"]["relevance"] = 0.5
        return cfg
        
    monkeypatch.setattr("advisor.ranking.scorer.load_config", mock_load_config)
    
    # baseline
    p = {"rrf_score": 1.0}
    context = {"min_rrf": 0, "max_rrf": 1}
    brk_baseline, tot_baseline = score_product(p, context)
    
    # Now register a dummy signal
    @ranking_signal("_dummy_signal")
    def dummy(product, context):
        return 1.0
        
    brk_dummy, tot_dummy = score_product(p, context)
    
    # The score should change and include _dummy_signal
    assert "_dummy_signal" in brk_dummy.weights_used
    assert brk_dummy.total != tot_baseline
