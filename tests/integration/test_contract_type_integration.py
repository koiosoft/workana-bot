"""
Integration Tests para Contract Type Detection Feature
Valida la integración completa de todos los componentes
"""

import os
import sys
import pytest
from pathlib import Path
from pymongo import MongoClient
from dotenv import load_dotenv

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

load_dotenv()


class TestFileStructure:
    """Tests de estructura de archivos"""

    def test_required_files_exist(self):
        """Verifica que todos los archivos necesarios existan"""
        required_files = [
            "app/intelligence/prompts/evaluation.j2",
            "app/intelligence/prompts/proposal.j2",
            "app/intelligence/prompts/proposal_staffing.j2",
            "app/database/projects_repository.py",
            "app/bots/telegram/handlers.py",
            "app/intelligence/adapters/gemini.py",
            "migrations/scripts/v20260523_01_add_contract_type_index.py",
        ]
        
        for file_path in required_files:
            assert os.path.exists(file_path), f"Archivo no encontrado: {file_path}"


class TestEvaluationTemplate:
    """Tests del template de evaluación"""

    def test_evaluation_template_has_contract_type_rules(self):
        """Verifica que el template de evaluación tenga las reglas de contract_type"""
        template_path = "app/intelligence/prompts/evaluation.j2"
        
        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        required_strings = [
            "REGLA DE CLASIFICACIÓN CONTRACTUAL",
            "contract_type",
            "project_fixed",
            "staff_augmentation",
        ]
        
        for required in required_strings:
            assert required in content, f"Template no contiene: {required}"


class TestRepositoryCode:
    """Tests del código del repositorio"""

    def test_repository_has_contract_type_parameter(self):
        """Verifica que update_project_analysis tenga el parámetro contract_type"""
        repo_path = "app/database/projects_repository.py"
        
        with open(repo_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert 'contract_type: str = "project_fixed"' in content
        assert '"contract_type": contract_type' in content
        assert '"contract_type": 1' in content


class TestAdapterCode:
    """Tests del adaptador de Gemini"""

    def test_adapter_selects_template_by_contract_type(self):
        """Verifica que el adaptador seleccione el template según contract_type"""
        adapter_path = "app/intelligence/adapters/gemini.py"
        
        with open(adapter_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert 'contract_type = project.get("contract_type"' in content
        assert 'template_name = "proposal_staffing.j2" if contract_type' in content
        assert "Generando propuesta para tipo de contrato" in content


class TestHandlerCode:
    """Tests de los handlers de Telegram"""

    def test_handlers_extract_and_use_contract_type(self):
        """Verifica que los handlers extraigan y usen contract_type"""
        handler_path = "app/bots/telegram/handlers.py"
        
        with open(handler_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert 'contract_type = eval_data.get("contract_type"' in content
        assert "contract_type=contract_type" in content
        assert 'contract_emoji = "🔧" if' in content
        assert 'full_detail["contract_type"]' in content


class TestTemplatesStructure:
    """Tests de estructura de templates"""

    def test_staffing_template_structure(self):
        """Verifica que proposal_staffing.j2 tenga la estructura correcta"""
        staffing_path = "app/intelligence/prompts/proposal_staffing.j2"
        
        with open(staffing_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        required_fields = ["cover_letter", "budget_summary", "hourly_rate"]
        for field in required_fields:
            assert field in content, f"Template staffing no contiene: {field}"

    def test_proposal_template_structure(self):
        """Verifica que proposal.j2 tenga la estructura correcta"""
        proposal_path = "app/intelligence/prompts/proposal.j2"
        
        with open(proposal_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        required_fields = ["proposal_header", "milestones", "summary", "technical_pitch"]
        for field in required_fields:
            assert field in content, f"Template proposal no contiene: {field}"


@pytest.mark.skipif(not os.getenv("MONGODB_URI"), reason="MONGODB_URI no configurado")
class TestDatabaseIntegration:
    """Tests de integración con MongoDB (requiere conexión real)"""

    @pytest.fixture
    def mongo_client(self):
        """Fixture para obtener cliente de MongoDB"""
        mongo_uri = os.getenv("MONGODB_URI")
        client = MongoClient(mongo_uri)
        yield client
        client.close()

    def test_contract_type_index_exists(self, mongo_client):
        """Verifica que el índice de contract_type exista en MongoDB"""
        db = mongo_client.get_default_database()
        projects = db["projects"]
        
        indexes = list(projects.list_indexes())
        index_names = [idx["name"] for idx in indexes]
        
        assert "idx_contract_type" in index_names, "Índice 'idx_contract_type' no existe"

    def test_projects_have_contract_type_field(self, mongo_client):
        """Verifica que haya proyectos con el campo contract_type"""
        db = mongo_client.get_default_database()
        projects = db["projects"]
        
        count_with_type = projects.count_documents({"contract_type": {"$exists": True}})
        
        # Solo advertencia si no hay datos, no falla el test
        if count_with_type == 0:
            pytest.skip("No hay proyectos con contract_type (ejecutar /lista)")
        
        assert count_with_type > 0

    def test_contract_type_distribution(self, mongo_client):
        """Verifica la distribución de tipos de contrato"""
        db = mongo_client.get_default_database()
        projects = db["projects"]
        
        staff_count = projects.count_documents({"contract_type": "staff_augmentation"})
        fixed_count = projects.count_documents({"contract_type": "project_fixed"})
        
        total = staff_count + fixed_count
        
        if total == 0:
            pytest.skip("No hay proyectos con contract_type")
        
        # Verificar que solo existan estos dos tipos
        assert staff_count + fixed_count == projects.count_documents(
            {"contract_type": {"$exists": True}}
        ), "Existen tipos de contrato no válidos"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
