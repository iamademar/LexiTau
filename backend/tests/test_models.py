import pytest
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models import Business, User, Document, Client, Project, Category
from app.enums import DocumentType, DocumentStatus, DocumentClassification, FileType
from app.test_db import engine, TestingSessionLocal, create_test_tables, drop_test_tables
import uuid


@pytest.fixture(scope="function")
def test_db():
    create_test_tables()
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        drop_test_tables()



class TestClient:
    def test_create_client(self, test_db: Session):
        business = Business(name="Test Business")
        test_db.add(business)
        test_db.commit()
        test_db.refresh(business)
        
        client = Client(
            business_id=business.id,
            name="Test Client Corp"
        )
        test_db.add(client)
        test_db.commit()
        test_db.refresh(client)
        
        assert client.id is not None
        assert client.business_id == business.id
        assert client.name == "Test Client Corp"
        assert client.created_at is not None

    def test_client_requires_business(self, test_db: Session):
        with pytest.raises(IntegrityError):
            client = Client(
                business_id=999,  # Non-existent business
                name="Test Client"
            )
            test_db.add(client)
            test_db.commit()

    def test_client_business_relationship(self, test_db: Session):
        business = Business(name="Test Business")
        test_db.add(business)
        test_db.commit()
        test_db.refresh(business)
        
        client = Client(
            business_id=business.id,
            name="Test Client"
        )
        test_db.add(client)
        test_db.commit()
        test_db.refresh(client)
        
        assert client.business.name == "Test Business"
        assert client.business.id == business.id

    def test_multiple_clients_same_business(self, test_db: Session):
        business = Business(name="Test Business")
        test_db.add(business)
        test_db.commit()
        test_db.refresh(business)
        
        client1 = Client(business_id=business.id, name="Client 1")
        client2 = Client(business_id=business.id, name="Client 2")
        
        test_db.add_all([client1, client2])
        test_db.commit()
        
        clients = test_db.query(Client).filter(Client.business_id == business.id).all()
        assert len(clients) == 2
        client_names = [client.name for client in clients]
        assert "Client 1" in client_names
        assert "Client 2" in client_names

    def test_clients_isolated_by_business(self, test_db: Session):
        business1 = Business(name="Business 1")
        business2 = Business(name="Business 2")
        test_db.add_all([business1, business2])
        test_db.commit()
        test_db.refresh(business1)
        test_db.refresh(business2)
        
        client1 = Client(business_id=business1.id, name="Client 1")
        client2 = Client(business_id=business2.id, name="Client 2")
        test_db.add_all([client1, client2])
        test_db.commit()
        
        business1_clients = test_db.query(Client).filter(Client.business_id == business1.id).all()
        business2_clients = test_db.query(Client).filter(Client.business_id == business2.id).all()
        
        assert len(business1_clients) == 1
        assert len(business2_clients) == 1
        assert business1_clients[0].name == "Client 1"
        assert business2_clients[0].name == "Client 2"


class TestProject:
    def test_create_project(self, test_db: Session):
        business = Business(name="Test Business")
        test_db.add(business)
        test_db.commit()
        test_db.refresh(business)
        
        project = Project(
            business_id=business.id,
            name="Website Redesign"
        )
        test_db.add(project)
        test_db.commit()
        test_db.refresh(project)
        
        assert project.id is not None
        assert project.business_id == business.id
        assert project.name == "Website Redesign"
        assert project.created_at is not None

    def test_project_requires_business(self, test_db: Session):
        with pytest.raises(IntegrityError):
            project = Project(
                business_id=999,  # Non-existent business
                name="Test Project"
            )
            test_db.add(project)
            test_db.commit()

    def test_project_business_relationship(self, test_db: Session):
        business = Business(name="Test Business")
        test_db.add(business)
        test_db.commit()
        test_db.refresh(business)
        
        project = Project(
            business_id=business.id,
            name="Test Project"
        )
        test_db.add(project)
        test_db.commit()
        test_db.refresh(project)
        
        assert project.business.name == "Test Business"
        assert project.business.id == business.id

    def test_multiple_projects_same_business(self, test_db: Session):
        business = Business(name="Test Business")
        test_db.add(business)
        test_db.commit()
        test_db.refresh(business)
        
        project1 = Project(business_id=business.id, name="Project Alpha")
        project2 = Project(business_id=business.id, name="Project Beta")
        
        test_db.add_all([project1, project2])
        test_db.commit()
        
        projects = test_db.query(Project).filter(Project.business_id == business.id).all()
        assert len(projects) == 2
        project_names = [project.name for project in projects]
        assert "Project Alpha" in project_names
        assert "Project Beta" in project_names

    def test_projects_isolated_by_business(self, test_db: Session):
        business1 = Business(name="Business 1")
        business2 = Business(name="Business 2")
        test_db.add_all([business1, business2])
        test_db.commit()
        test_db.refresh(business1)
        test_db.refresh(business2)
        
        project1 = Project(business_id=business1.id, name="Project 1")
        project2 = Project(business_id=business2.id, name="Project 2")
        test_db.add_all([project1, project2])
        test_db.commit()
        
        business1_projects = test_db.query(Project).filter(Project.business_id == business1.id).all()
        business2_projects = test_db.query(Project).filter(Project.business_id == business2.id).all()
        
        assert len(business1_projects) == 1
        assert len(business2_projects) == 1
        assert business1_projects[0].name == "Project 1"
        assert business2_projects[0].name == "Project 2"


class TestCategory:
    def test_create_category(self, test_db: Session):
        category = Category(name="Office Supplies")
        test_db.add(category)
        test_db.commit()
        test_db.refresh(category)
        
        assert category.id is not None
        assert category.name == "Office Supplies"
        assert category.created_at is not None

    def test_category_name_unique(self, test_db: Session):
        category1 = Category(name="Software")
        test_db.add(category1)
        test_db.commit()
        
        with pytest.raises(IntegrityError):
            category2 = Category(name="Software")  # Same name
            test_db.add(category2)
            test_db.commit()

    def test_multiple_unique_categories(self, test_db: Session):
        categories = [
            Category(name="Travel"),
            Category(name="Equipment"),
            Category(name="Marketing"),
            Category(name="Utilities")
        ]
        test_db.add_all(categories)
        test_db.commit()
        
        all_categories = test_db.query(Category).all()
        assert len(all_categories) == 4
        
        category_names = [cat.name for cat in all_categories]
        assert "Travel" in category_names
        assert "Equipment" in category_names
        assert "Marketing" in category_names
        assert "Utilities" in category_names

    def test_categories_are_global(self, test_db: Session):
        # Categories should be accessible regardless of business
        business1 = Business(name="Business 1")
        business2 = Business(name="Business 2")
        test_db.add_all([business1, business2])
        test_db.commit()
        
        category = Category(name="Fuel")
        test_db.add(category)
        test_db.commit()
        test_db.refresh(category)
        
        # Both businesses should be able to see the same category
        all_categories = test_db.query(Category).all()
        assert len(all_categories) == 1
        assert all_categories[0].name == "Fuel"
        
        # Category should not be tied to any specific business
        assert not hasattr(category, 'business_id')


class TestBusinessTagsIntegration:
    """Test the relationship between businesses and their tags (clients/projects)"""
    
    def test_business_with_clients_and_projects(self, test_db: Session):
        business = Business(name="Full Service Business")
        test_db.add(business)
        test_db.commit()
        test_db.refresh(business)
        
        # Add clients
        client1 = Client(business_id=business.id, name="ABC Corp")
        client2 = Client(business_id=business.id, name="XYZ Inc")
        
        # Add projects
        project1 = Project(business_id=business.id, name="Website Development")
        project2 = Project(business_id=business.id, name="Mobile App")
        
        # Add global categories
        category1 = Category(name="Development")
        category2 = Category(name="Consulting")
        
        test_db.add_all([client1, client2, project1, project2, category1, category2])
        test_db.commit()
        
        # Verify all tags per business
        business_clients = test_db.query(Client).filter(Client.business_id == business.id).all()
        business_projects = test_db.query(Project).filter(Project.business_id == business.id).all()
        all_categories = test_db.query(Category).all()
        
        assert len(business_clients) == 2
        assert len(business_projects) == 2
        assert len(all_categories) == 2
        
        client_names = [client.name for client in business_clients]
        project_names = [project.name for project in business_projects]
        category_names = [category.name for category in all_categories]
        
        assert "ABC Corp" in client_names
        assert "XYZ Inc" in client_names
        assert "Website Development" in project_names
        assert "Mobile App" in project_names
        assert "Development" in category_names
        assert "Consulting" in category_names


