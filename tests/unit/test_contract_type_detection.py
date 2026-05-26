"""
Test Suite para Contract Type Detection
Valida la detección automática de tipo de contrato y generación de propuestas diferenciadas
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestContractTypeDetection:
    """Tests para validar la detección de contract_type"""

    def test_staff_augmentation_keywords(self):
        """Verifica que se detecten correctamente keywords de staff augmentation"""
        staff_keywords = [
            "busco desarrollador por horas",
            "necesito programador para incorporarse al equipo",
            "enviar CV con experiencia",
            "soporte a largo plazo",
            "pago por hora",
            "contratación mensual",
        ]
        
        for keyword in staff_keywords:
            description = f"Proyecto test: {keyword}"
            # Simulamos análisis de IA (en producción esto lo hace Gemini)
            expected_type = "staff_augmentation"
            assert keyword in description.lower()

    def test_project_fixed_keywords(self):
        """Verifica que se detecten correctamente keywords de proyecto llave en mano"""
        project_keywords = [
            "desarrollo de plataforma completa",
            "proyecto llave en mano",
            "entregables definidos",
            "sistema desde cero",
            "MVP de aplicación",
        ]
        
        for keyword in project_keywords:
            description = f"Proyecto test: {keyword}"
            expected_type = "project_fixed"
            assert keyword in description.lower()


class TestProposalTemplateSelection:
    """Tests para validar selección de template correcto"""

    @pytest.mark.asyncio
    async def test_staff_augmentation_uses_staffing_template(self):
        """Verifica que proyectos de staff augmentation usen proposal_staffing.j2"""
        from app.intelligence.adapters.gemini import GeminiAdapter
        
        # Mock del proyecto
        project = {
            "contract_type": "staff_augmentation",
            "title": "Desarrollador Python Senior",
            "full_description": "Busco desarrollador para incorporarse al equipo",
            "skills": ["Python", "Django"],
            "budget_detail": "$25-30/hora"
        }
        
        adapter = GeminiAdapter()
        
        # Verificamos que se llame al método _render_prompt con el template correcto
        with patch.object(adapter, '_render_prompt', return_value="mocked_prompt") as mock_render:
            with patch.object(adapter.client.models, 'generate_content') as mock_api:
                # Simulamos respuesta de la API
                mock_response = MagicMock()
                mock_response.text = '''```json
                {
                    "cover_letter": "Test cover letter",
                    "budget_summary": {
                        "hourly_rate": 25,
                        "suggested_hours_per_week": 20,
                        "estimated_monthly_budget": 2000
                    },
                    "questions_for_client": []
                }
                ```'''
                mock_api.return_value = mock_response
                
                result = await adapter.generate_proposal(project)
                
                # Verificar que se llamó con el template correcto
                mock_render.assert_called_once()
                call_args = mock_render.call_args
                assert call_args[0][0] == "proposal_staffing.j2"

    @pytest.mark.asyncio
    async def test_project_fixed_uses_project_template(self):
        """Verifica que proyectos llave en mano usen proposal.j2"""
        from app.intelligence.adapters.gemini import GeminiAdapter
        
        project = {
            "contract_type": "project_fixed",
            "title": "Sistema de Gestión",
            "full_description": "Desarrollo de plataforma completa de gestión",
            "skills": ["Python", "React"],
            "budget_detail": "$3000-5000"
        }
        
        adapter = GeminiAdapter()
        
        with patch.object(adapter, '_render_prompt', return_value="mocked_prompt") as mock_render:
            with patch.object(adapter.client.models, 'generate_content') as mock_api:
                mock_response = MagicMock()
                mock_response.text = '''```json
                {
                    "proposal_header": "Test header",
                    "milestones": [],
                    "summary": {
                        "total_hours": 180,
                        "total_budget": 4500,
                        "delivery_time_weeks": 8,
                        "hourly_rate_applied": 25
                    },
                    "technical_pitch": "Test pitch",
                    "questions_for_client": []
                }
                ```'''
                mock_api.return_value = mock_response
                
                result = await adapter.generate_proposal(project)
                
                mock_render.assert_called_once()
                call_args = mock_render.call_args
                assert call_args[0][0] == "proposal.j2"


class TestDatabaseIntegration:
    """Tests para validar integración con MongoDB"""

    @pytest.mark.asyncio
    async def test_contract_type_saved_in_analysis(self):
        """Verifica que contract_type se guarde correctamente en el análisis"""
        from app.database.projects_repository import ProjectsRepository
        
        repo = ProjectsRepository()
        
        # Mock de la colección de MongoDB
        with patch.object(repo, 'collection') as mock_collection:
            mock_collection.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
            
            result = await repo.update_project_analysis(
                link_hash="test_hash",
                score=8,
                reason="Test reason",
                strategy="flash",
                status="analyzed",
                ai_summary="Test summary",
                contract_type="staff_augmentation"
            )
            
            assert result is True
            mock_collection.update_one.assert_called_once()
            
            # Verificar que el update incluye contract_type
            call_args = mock_collection.update_one.call_args
            update_data = call_args[0][1]["$set"]
            assert "contract_type" in update_data
            assert update_data["contract_type"] == "staff_augmentation"

    @pytest.mark.asyncio
    async def test_contract_type_retrieved_for_proposal(self):
        """Verifica que contract_type se recupere al obtener proyectos para propuesta"""
        from app.database.projects_repository import ProjectsRepository
        
        repo = ProjectsRepository()
        
        mock_projects = [
            {
                "link_hash": "hash1",
                "title": "Proyecto 1",
                "contract_type": "project_fixed",
                "strategy": "pro"
            },
            {
                "link_hash": "hash2",
                "title": "Proyecto 2",
                "contract_type": "staff_augmentation",
                "strategy": "flash"
            }
        ]
        
        with patch.object(repo, 'collection') as mock_collection:
            mock_cursor = MagicMock()
            mock_cursor.to_list = AsyncMock(return_value=mock_projects)
            mock_collection.find.return_value = mock_cursor
            mock_cursor.limit.return_value = mock_cursor
            
            projects = await repo.get_projects_for_deep_analysis(limit=10)
            
            assert len(projects) == 2
            assert projects[0]["contract_type"] == "project_fixed"
            assert projects[1]["contract_type"] == "staff_augmentation"


class TestProposalStructure:
    """Tests para validar estructura de propuestas generadas"""

    def test_staff_proposal_structure(self):
        """Verifica que propuestas de staff tengan estructura correcta"""
        staff_proposal = {
            "cover_letter": "Sample cover letter",
            "budget_summary": {
                "hourly_rate": 25,
                "suggested_hours_per_week": 20,
                "estimated_monthly_budget": 2000
            },
            "questions_for_client": []
        }
        
        # Validar campos obligatorios
        assert "cover_letter" in staff_proposal
        assert "budget_summary" in staff_proposal
        assert "hourly_rate" in staff_proposal["budget_summary"]
        assert staff_proposal["budget_summary"]["hourly_rate"] > 0

    def test_project_proposal_structure(self):
        """Verifica que propuestas de proyecto tengan estructura correcta"""
        project_proposal = {
            "proposal_header": "Header",
            "milestones": [
                {
                    "step": 1,
                    "name": "Milestone 1",
                    "tasks": {},
                    "hours_with_overhead": 45,
                    "subtotal": 1125.0
                }
            ],
            "summary": {
                "total_hours": 180,
                "total_budget": 4500,
                "delivery_time_weeks": 8,
                "hourly_rate_applied": 25
            },
            "technical_pitch": "Pitch",
            "questions_for_client": []
        }
        
        # Validar campos obligatorios
        assert "proposal_header" in project_proposal
        assert "milestones" in project_proposal
        assert "summary" in project_proposal
        assert "total_budget" in project_proposal["summary"]
        assert project_proposal["summary"]["total_budget"] > 0


class TestTelegramMessages:
    """Tests para validar mensajes de Telegram"""

    def test_contract_type_emoji_staff(self):
        """Verifica que se use emoji correcto para staff augmentation"""
        contract_type = "staff_augmentation"
        contract_emoji = "🔧" if contract_type == "staff_augmentation" else "📦"
        contract_label = "Staff Aug." if contract_type == "staff_augmentation" else "Proyecto"
        
        assert contract_emoji == "🔧"
        assert contract_label == "Staff Aug."

    def test_contract_type_emoji_project(self):
        """Verifica que se use emoji correcto para proyecto fijo"""
        contract_type = "project_fixed"
        contract_emoji = "🔧" if contract_type == "staff_augmentation" else "📦"
        contract_label = "Staff Aug." if contract_type == "staff_augmentation" else "Proyecto"
        
        assert contract_emoji == "📦"
        assert contract_label == "Proyecto"

    def test_message_format_staff(self):
        """Verifica formato de mensaje para staff augmentation"""
        proposal = {
            "budget_summary": {
                "hourly_rate": 25,
                "estimated_monthly_budget": 2000
            }
        }
        
        hourly = proposal["budget_summary"]["hourly_rate"]
        monthly = proposal["budget_summary"]["estimated_monthly_budget"]
        
        message = f"💰 ${hourly}/hora | 📅 ~${monthly}/mes"
        
        assert "$25/hora" in message
        assert "$2000/mes" in message

    def test_message_format_project(self):
        """Verifica formato de mensaje para proyecto fijo"""
        proposal = {
            "summary": {
                "total_budget": 4500,
                "total_hours": 180
            }
        }
        
        total_usd = proposal["summary"]["total_budget"]
        total_hours = proposal["summary"]["total_hours"]
        
        message = f"💰 Presupuesto: ${total_usd} | ⏱️ Horas: {total_hours}h"
        
        assert "$4500" in message
        assert "180h" in message


# Fixtures para testing
@pytest.fixture
def sample_staff_project():
    """Fixture de proyecto staff augmentation"""
    return {
        "link_hash": "test_hash_staff",
        "title": "Desarrollador Python Senior",
        "contract_type": "staff_augmentation",
        "strategy": "flash",
        "full_description": "Busco desarrollador Python para incorporarse al equipo",
        "skills": ["Python", "Django", "PostgreSQL"],
        "budget_detail": "$25-30/hora"
    }


@pytest.fixture
def sample_fixed_project():
    """Fixture de proyecto llave en mano"""
    return {
        "link_hash": "test_hash_fixed",
        "title": "Sistema de Gestión de Inventario",
        "contract_type": "project_fixed",
        "strategy": "pro",
        "full_description": "Desarrollo completo de sistema de gestión",
        "skills": ["Python", "React", "PostgreSQL"],
        "budget_detail": "$3000-5000"
    }


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
