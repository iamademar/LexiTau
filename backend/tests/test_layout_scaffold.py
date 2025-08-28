def test_layer_imports():
    """Test that all layer packages can be imported successfully."""
    import app.routers
    import app.models
    import app.schemas
    import app.services
    import app.dependencies
    
    assert app.dependencies.ping() == "ok"


def test_schema_imports():
    """Test that new schema classes can be imported from package level."""
    from app.schemas import UserBase, ItemBase
    
    # Test that they are proper Pydantic models
    user = UserBase(email="test@example.com")
    assert user.email == "test@example.com"
    
    item = ItemBase(name="test_item")
    assert item.name == "test_item"


def test_existing_schema_imports():
    """Test that existing schema classes still work with package imports."""
    from app.schemas import SignupRequest, DocumentResponse
    
    # Test that classes can be imported without error
    assert SignupRequest is not None
    assert DocumentResponse is not None