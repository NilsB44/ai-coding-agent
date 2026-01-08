from RAG.sandbox.my_fibonacci import fibonacci_recursive, fibonacci_iterative

def test_feature():
    assert fibonacci_recursive(9) == 21
    assert fibonacci_iterative(9) == 21
    assert fibonacci_recursive(-1) == -1
    assert fibonacci_iterative(-1) == -1
    assert fibonacci_recursive(0) == 0
    
test_feature()