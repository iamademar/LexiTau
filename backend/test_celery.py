#!/usr/bin/env python3
"""
Test script for Celery task queueing and result return
"""

import time
from app.tasks.test_tasks import add, multiply
from app.tasks.document_tasks import process_document_ocr, process_document_classification
import uuid


def test_basic_tasks():
    """Test basic arithmetic tasks"""
    print("Testing basic arithmetic tasks...")
    
    # Test add task
    print("Dispatching add(4, 5) task...")
    task_result = add.delay(4, 5)
    print(f"Task ID: {task_result.id}")
    
    # Wait for result
    result = task_result.get(timeout=10)
    print(f"Result: {result}")
    assert result == 9, f"Expected 9, got {result}"
    
    # Test multiply task
    print("Dispatching multiply(3, 7) task...")
    task_result = multiply.delay(3, 7)
    print(f"Task ID: {task_result.id}")
    
    # Wait for result
    result = task_result.get(timeout=10)
    print(f"Result: {result}")
    assert result == 21, f"Expected 21, got {result}"
    
    print("✅ Basic tasks completed successfully")


def test_document_tasks():
    """Test document processing tasks"""
    print("\nTesting document processing tasks...")
    
    test_doc_id = str(uuid.uuid4())
    
    # Test OCR task
    print(f"Dispatching OCR task for document {test_doc_id}...")
    ocr_task = process_document_ocr.delay(test_doc_id)
    print(f"OCR Task ID: {ocr_task.id}")
    
    # Wait for OCR result
    ocr_result = ocr_task.get(timeout=15)
    print(f"OCR Result: {ocr_result}")
    assert ocr_result["document_id"] == test_doc_id
    assert ocr_result["status"] == "completed"
    
    # Test classification task
    print(f"Dispatching classification task for document {test_doc_id}...")
    class_task = process_document_classification.delay(test_doc_id)
    print(f"Classification Task ID: {class_task.id}")
    
    # Wait for classification result
    class_result = class_task.get(timeout=10)
    print(f"Classification Result: {class_result}")
    assert class_result["document_id"] == test_doc_id
    assert class_result["document_type"] == "invoice"
    
    print("✅ Document tasks completed successfully")


def test_async_behavior():
    """Test asynchronous behavior"""
    print("\nTesting asynchronous behavior...")
    
    # Dispatch multiple tasks without waiting
    tasks = []
    for i in range(5):
        task = add.delay(i, i * 2)
        tasks.append((task, i + i * 2))  # Store expected result
        print(f"Dispatched task {task.id}: add({i}, {i * 2})")
    
    # Collect results
    for task, expected in tasks:
        result = task.get(timeout=10)
        print(f"Task {task.id} result: {result} (expected: {expected})")
        assert result == expected, f"Expected {expected}, got {result}"
    
    print("✅ Async behavior test completed successfully")


if __name__ == "__main__":
    print("🚀 Starting Celery connectivity tests...")
    
    try:
        test_basic_tasks()
        test_document_tasks()
        test_async_behavior()
        
        print("\n🎉 All tests passed! Celery and Redis are working correctly.")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        raise