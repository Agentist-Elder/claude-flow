# InciteRewrite London School TDD Test Suite

A comprehensive test suite implementing London School (mockist) Test-Driven Development methodology for the InciteRewrite legal citation verification system.

## 🎯 London School TDD Principles

This test suite follows the **London School** approach to TDD, which emphasizes:

- **Outside-In Development**: Starting from user behavior and working down to implementation details
- **Mock-Driven Development**: Using mocks to define contracts and isolate units under test
- **Behavior Verification**: Focusing on HOW objects collaborate rather than WHAT they contain
- **Interaction Testing**: Verifying the conversations between objects
- **Contract Definition**: Using mock expectations to establish clear interfaces

## 📁 Test Structure

```
tests/
├── conftest.py                 # Main pytest configuration and fixtures
├── conftest_extended.py        # Extended fixtures for comprehensive testing
├── mock_utilities.py          # Mock objects and behavior verification utilities
├── pytest.ini                 # Pytest configuration file
├── run_tests.py               # Comprehensive test runner
├── test_app.py                # Flask application behavior tests
├── test_processor.py          # Document processing interaction tests
├── test_citations.py          # Citation extraction behavior tests
├── test_courtlistener.py      # API client interaction tests
├── test_storage.py            # Database operation behavior tests
└── test_integration.py        # End-to-end workflow tests
```

## 🚀 Running Tests

### Quick Start

```bash
# Run all tests
python tests/run_tests.py all

# Run fast tests for development
python tests/run_tests.py fast

# Run with coverage
python tests/run_tests.py coverage
```

### Test Categories

```bash
# Unit tests (isolated component behavior)
python tests/run_tests.py unit

# Integration tests (component interactions)
python tests/run_tests.py integration

# End-to-end tests (complete workflows)
python tests/run_tests.py e2e

# Performance tests
python tests/run_tests.py performance

# Behavior verification showcase
python tests/run_tests.py showcase
```

### Using pytest directly

```bash
# Run tests with specific markers
pytest -m "unit and not slow"
pytest -m "integration and auth"
pytest -m "citation and legal"

# Run tests matching patterns
pytest -k "test_behavior"
pytest -k "test_collaboration"

# Run specific test files
pytest tests/test_app.py::TestAuthenticationMiddleware
pytest tests/test_integration.py -v
```

## 📊 Test Categories and Markers

### Primary Categories
- `unit` - Unit tests focusing on individual components
- `integration` - Integration tests for component interactions
- `e2e` - End-to-end tests for complete workflows
- `performance` - Performance and scalability tests

### Feature Areas
- `auth` - Authentication and authorization tests
- `text_processing` - Text analysis and processing tests
- `database` - Database operations and storage tests
- `api` - HTTP API endpoint tests
- `citation` - Legal citation processing tests
- `legal` - Legal document handling tests

### Test Characteristics
- `fast` - Quick tests (<100ms) for development
- `slow` - Longer running tests (>1s)
- `mock` - Tests using mock objects
- `real` - Tests using real implementations
- `concurrency` - Concurrent execution tests
- `security` - Security-focused tests

## 🎭 Mock Objects and Behavior Verification

### London School Mock Implementation

The test suite includes sophisticated mock objects that focus on behavior verification:

```python
# Example: Verifying authentication workflow
def test_user_registration_workflow(self):
    """Should coordinate user registration with proper collaborations."""
    auth_manager = MockAuthenticationManager()
    user_service = UserService(auth_manager, mock_email_service)
    
    # Act
    result = user_service.register_user("john", "john@example.com", "password")
    
    # Verify collaborations
    auth_manager.register_user.assert_called_once_with("john", "john@example.com", "password")
    mock_email_service.send_welcome_email.assert_called_once_with(result.user_id)
```

### Behavior Verification Features

- **Interaction Logging**: All mock interactions are logged for verification
- **Collaboration Verification**: Verify the sequence of object collaborations
- **Contract Definition**: Mock expectations define component interfaces
- **Realistic Behavior**: Mocks simulate real component behavior patterns

## 📝 Test Files Overview

### test_app.py - Flask Application Tests
- HTTP middleware behavior verification
- Authentication workflow testing
- API endpoint interaction patterns
- Error handling and response behavior
- Session management across requests

### test_processor.py - Document Processing Tests
- Text analysis behavior verification
- Component collaboration patterns
- Database integration testing
- Performance characteristic validation
- Error handling and edge cases

### test_citations.py - Citation Extraction Tests
- Legal citation pattern recognition
- Citation validation behavior
- Extraction accuracy verification
- Format normalization testing
- Confidence scoring validation

### test_courtlistener.py - API Client Tests
- HTTP client behavior verification
- API interaction patterns
- Rate limiting compliance
- Error handling and recovery
- Response processing behavior

### test_storage.py - Database Operation Tests
- Database connection management
- Query execution behavior
- Transaction handling patterns
- Performance monitoring
- Concurrent access testing

### test_integration.py - End-to-End Tests
- Complete user workflows
- System component integration
- Cross-service collaboration
- Performance under load
- Error recovery scenarios

## 🔧 Test Fixtures and Utilities

### Database Fixtures
- `temp_db_path` - Temporary database for persistent tests
- `memory_db` - In-memory database for fast tests
- `db_manager` - Configured database manager
- `db_validator` - Database state verification utilities

### Authentication Fixtures
- `auth_manager` - Authentication service instance
- `registered_user` - Pre-registered test user
- `authenticated_user` - User with valid session token
- `sample_user_data` - Consistent test user data

### Application Fixtures
- `test_app` - Configured Flask application
- `client` - HTTP test client
- `authenticated_user` - API client with auth headers

### Mock Fixtures
- `mock_courtlistener_client` - CourtListener API mock
- `mock_citation_extractor` - Citation extraction mock
- `mock_external_services` - Complete external service mocks

### Utility Fixtures
- `performance_monitor` - Performance measurement utilities
- `data_generator` - Test data generation utilities
- `concurrent_test_helper` - Concurrency testing utilities

## 🎯 London School TDD Examples

### 1. Outside-In Development

```python
def test_complete_document_analysis_workflow(self):
    """Should support complete workflow from user registration to document analysis."""
    # Start from user behavior (outside)
    user_service = UserService(mock_auth, mock_processor, mock_storage)
    
    # Act
    result = user_service.analyze_document(user_data, document_text)
    
    # Verify the collaboration chain (working inward)
    mock_auth.validate_user.assert_called_once()
    mock_processor.analyze_text.assert_called_once_with(document_text)
    mock_storage.store_analysis.assert_called_once()
```

### 2. Behavior Verification Over State

```python
def test_coordinates_citation_verification_workflow(self):
    """Should coordinate citation verification with external API."""
    citation_service = CitationService(mock_extractor, mock_api_client)
    
    # Act
    result = citation_service.verify_document_citations(legal_text)
    
    # Verify HOW objects collaborate
    assert mock_extractor.extract_citations.called
    assert mock_api_client.verify_citation.call_count == len(extracted_citations)
    
    # Verify conversation sequence
    call_sequence = [
        call.mock_extractor.extract_citations(legal_text),
        call.mock_api_client.verify_citation(citation_1),
        call.mock_api_client.verify_citation(citation_2)
    ]
    assert mock_manager.call_history == call_sequence
```

### 3. Mock-Driven Contract Definition

```python
def test_defines_text_processor_contract(self):
    """Should define contract for text processing collaboration."""
    # Mock defines the expected interface
    mock_processor = Mock(spec=TextProcessor)
    mock_processor.analyze_text.return_value = Mock(
        word_count=100,
        sentiment_score=0.5,
        processing_time=0.1
    )
    
    # System under test uses the contract
    document_service = DocumentService(mock_processor)
    result = document_service.process_document(sample_text)
    
    # Verify contract compliance
    mock_processor.analyze_text.assert_called_once_with(
        sample_text, 
        store_result=True
    )
```

## 🚦 Continuous Integration

### GitHub Actions Configuration

```yaml
name: London School TDD Test Suite

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.8, 3.9, 3.10, 3.11]
        test-type: [unit, integration, e2e]
    
    steps:
    - uses: actions/checkout@v3
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-cov pytest-xdist
    
    - name: Run ${{ matrix.test-type }} tests
      run: |
        python tests/run_tests.py ${{ matrix.test-type }}
```

## 📈 Coverage and Quality Metrics

### Coverage Targets
- **Unit Tests**: >95% line coverage
- **Integration Tests**: >85% branch coverage  
- **E2E Tests**: >90% feature coverage

### Quality Metrics
- **Behavior Verification**: All critical interactions tested
- **Contract Coverage**: All component interfaces mocked and verified
- **Error Path Testing**: All exception paths covered
- **Performance Validation**: Response times and resource usage verified

## 🛠 Development Guidelines

### Writing London School Tests

1. **Start with Behavior**: Focus on what the system should do, not how it's implemented
2. **Mock Collaborators**: Use mocks for all external dependencies
3. **Verify Interactions**: Assert on method calls and collaboration patterns
4. **Define Contracts**: Use mock expectations to specify component interfaces
5. **Test Conversations**: Verify the sequence of object interactions

### Mock Object Guidelines

1. **Realistic Behavior**: Mocks should behave like real objects
2. **Contract Compliance**: Mock interfaces should match real implementations
3. **Interaction Logging**: Log all interactions for verification
4. **Failure Simulation**: Include realistic failure scenarios
5. **Performance Simulation**: Include realistic timing behavior

### Test Organization

1. **One Behavior Per Test**: Each test verifies a single behavior
2. **Clear Test Names**: Names should describe the behavior being tested
3. **Arrange-Act-Assert**: Follow the standard test structure
4. **Mock Setup**: Set up mocks before the action
5. **Behavior Verification**: Verify interactions after the action

## 🔍 Troubleshooting

### Common Issues

1. **Mock Not Called**: Check that the mock is properly injected
2. **Wrong Call Arguments**: Verify the expected parameters
3. **Call Sequence Issues**: Check the order of mock interactions
4. **Async Test Issues**: Use appropriate async test fixtures
5. **Database Issues**: Ensure proper database cleanup

### Debug Mode

```bash
# Run tests with debug information
python tests/run_tests.py all --debug --verbose

# Run specific failing test with full traceback
pytest tests/test_app.py::TestClass::test_method -vvv --tb=long
```

## 📚 Further Reading

- [London School TDD Guide](https://github.com/testdouble/contributing-tests/wiki/London-school-TDD)
- [Mock Objects Pattern](https://martinfowler.com/articles/mocksArentStubs.html)
- [Behavior Verification](https://martinfowler.com/bliki/BehaviorDrivenDevelopment.html)
- [Outside-In Development](https://www.goodreads.com/book/show/4268826-growing-object-oriented-software)

---

**Remember**: London School TDD focuses on the **conversations between objects**. Test how your objects collaborate, not what they contain! 🎭✨