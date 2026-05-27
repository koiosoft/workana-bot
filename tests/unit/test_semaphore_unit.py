"""
Tests unitarios para el sistema de semáforo global.
Estos tests verifican la lógica interna sin dependencias de MongoDB.
Ejecutar con: pytest tests/unit/test_semaphore_unit.py -v
"""
import pytest
from datetime import datetime, timezone
from app.database.semaphore import ProcessSemaphore


class TestSemaphoreCalculations:
    """Tests de métodos de cálculo sin dependencias de BD."""
    
    def test_calculate_remaining_projects_normal(self):
        """Test: Cálculo normal de proyectos restantes."""
        semaphore = ProcessSemaphore()
        status = {
            "total_projects": 50,
            "processed_count": 30,
            "failed_count": 5,
            "not_found_count": 3
        }
        
        remaining = semaphore.calculate_remaining_projects(status)
        assert remaining == 12, "Debería calcular 50 - 30 - 5 - 3 = 12"
    
    def test_calculate_remaining_projects_zero(self):
        """Test: Todos los proyectos procesados."""
        semaphore = ProcessSemaphore()
        status = {
            "total_projects": 20,
            "processed_count": 15,
            "failed_count": 3,
            "not_found_count": 2
        }
        
        remaining = semaphore.calculate_remaining_projects(status)
        assert remaining == 0, "No deberían quedar proyectos"
    
    def test_calculate_remaining_projects_negative_protection(self):
        """Test: Protección contra valores negativos."""
        semaphore = ProcessSemaphore()
        status = {
            "total_projects": 10,
            "processed_count": 8,
            "failed_count": 5,
            "not_found_count": 3
        }
        
        remaining = semaphore.calculate_remaining_projects(status)
        assert remaining == 0, "Debería retornar 0 en lugar de negativo"
        assert remaining >= 0, "Nunca debe retornar valores negativos"
    
    def test_calculate_remaining_projects_missing_keys(self):
        """Test: Manejo de claves faltantes en el status."""
        semaphore = ProcessSemaphore()
        status = {
            "total_projects": 50
        }
        
        remaining = semaphore.calculate_remaining_projects(status)
        assert remaining == 50, "Debería asumir 0 para contadores faltantes"
    
    def test_calculate_remaining_projects_empty_status(self):
        """Test: Status vacío."""
        semaphore = ProcessSemaphore()
        status = {}
        
        remaining = semaphore.calculate_remaining_projects(status)
        assert remaining == 0, "Status vacío debería retornar 0"


class TestTelemetryFormatting:
    """Tests del formateo de mensajes de telemetría."""
    
    def test_format_telemetry_message_complete(self):
        """Test: Mensaje de telemetría con todos los datos."""
        semaphore = ProcessSemaphore()
        
        locked_at = datetime(2024, 1, 15, 14, 30, 0, tzinfo=timezone.utc)
        last_activity = datetime(2024, 1, 15, 14, 45, 23, tzinfo=timezone.utc)
        
        status = {
            "is_locked": True,
            "locked_at": locked_at,
            "last_activity_at": last_activity,
            "total_projects": 50,
            "processed_count": 12,
            "failed_count": 2,
            "not_found_count": 1
        }
        
        message = semaphore.format_telemetry_message(status)
        
        # Verificar elementos clave del mensaje
        assert "BLOQUEADO" in message
        assert "Bloqueado desde:" in message
        assert "2024-01-15 14:30:00 UTC" in message
        assert "Última actividad:" in message
        assert "2024-01-15 14:45:23 UTC" in message
        assert "Proyectos restantes:" in message
        assert "35/50" in message  # 50 - 12 - 2 - 1
        assert "Procesados: 12" in message
        assert "Fallidos: 2" in message
        assert "No encontrados: 1" in message
    
    def test_format_telemetry_message_no_dates(self):
        """Test: Mensaje sin fechas (None)."""
        semaphore = ProcessSemaphore()
        
        status = {
            "is_locked": True,
            "locked_at": None,
            "last_activity_at": None,
            "total_projects": 100,
            "processed_count": 0,
            "failed_count": 0,
            "not_found_count": 0
        }
        
        message = semaphore.format_telemetry_message(status)
        
        assert "N/A" in message
        assert "100/100" in message
        assert "Procesados: 0" in message
    
    def test_format_telemetry_message_partial_progress(self):
        """Test: Mensaje con progreso parcial."""
        semaphore = ProcessSemaphore()
        
        status = {
            "is_locked": True,
            "locked_at": datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
            "last_activity_at": datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
            "total_projects": 200,
            "processed_count": 150,
            "failed_count": 10,
            "not_found_count": 5
        }
        
        message = semaphore.format_telemetry_message(status)
        
        assert "35/200" in message  # 200 - 150 - 10 - 5
        assert "Procesados: 150" in message
        assert "Fallidos: 10" in message
        assert "No encontrados: 5" in message
    
    def test_format_telemetry_message_all_processed(self):
        """Test: Mensaje cuando todos están procesados."""
        semaphore = ProcessSemaphore()
        
        status = {
            "is_locked": True,
            "locked_at": datetime.now(timezone.utc),
            "last_activity_at": datetime.now(timezone.utc),
            "total_projects": 10,
            "processed_count": 8,
            "failed_count": 1,
            "not_found_count": 1
        }
        
        message = semaphore.format_telemetry_message(status)
        
        assert "0/10" in message  # Todos procesados
    
    def test_format_telemetry_message_markdown_format(self):
        """Test: Verificar que el mensaje tiene formato Markdown."""
        semaphore = ProcessSemaphore()
        
        status = {
            "is_locked": True,
            "locked_at": datetime.now(timezone.utc),
            "last_activity_at": datetime.now(timezone.utc),
            "total_projects": 25,
            "processed_count": 10,
            "failed_count": 2,
            "not_found_count": 1
        }
        
        message = semaphore.format_telemetry_message(status)
        
        # Verificar formato Markdown
        assert "**BLOQUEADO**" in message
        assert "**Bloqueado desde:**" in message
        assert "**Última actividad:**" in message
        assert "**Proyectos restantes:**" in message


class TestSemaphoreConstants:
    """Tests de constantes y configuración."""
    
    def test_collection_name(self):
        """Test: Nombre de la colección."""
        assert ProcessSemaphore.COLLECTION_NAME == "process_semaphore"
    
    def test_lock_id(self):
        """Test: ID del bloqueo."""
        assert ProcessSemaphore.LOCK_ID == "proposal_generation_lock"
    
    def test_indexes_ready_initial_state(self):
        """Test: Estado inicial de _indexes_ready."""
        semaphore = ProcessSemaphore()
        assert semaphore._indexes_ready is False


class TestSemaphoreEdgeCases:
    """Tests de casos extremos y límites."""
    
    def test_calculate_remaining_with_large_numbers(self):
        """Test: Cálculo con números grandes."""
        semaphore = ProcessSemaphore()
        status = {
            "total_projects": 10000,
            "processed_count": 7500,
            "failed_count": 1250,
            "not_found_count": 750
        }
        
        remaining = semaphore.calculate_remaining_projects(status)
        assert remaining == 500
    
    def test_calculate_remaining_with_zero_total(self):
        """Test: Total de proyectos es cero."""
        semaphore = ProcessSemaphore()
        status = {
            "total_projects": 0,
            "processed_count": 0,
            "failed_count": 0,
            "not_found_count": 0
        }
        
        remaining = semaphore.calculate_remaining_projects(status)
        assert remaining == 0
    
    def test_format_telemetry_with_string_dates(self):
        """Test: Fechas como strings en lugar de datetime."""
        semaphore = ProcessSemaphore()
        
        status = {
            "is_locked": True,
            "locked_at": "2024-01-15T14:30:00Z",
            "last_activity_at": "2024-01-15T14:45:00Z",
            "total_projects": 50,
            "processed_count": 25,
            "failed_count": 3,
            "not_found_count": 2
        }
        
        message = semaphore.format_telemetry_message(status)
        
        # Debería manejar strings sin fallar
        assert "BLOQUEADO" in message
        assert "2024-01-15T14:30:00Z" in message
        assert "20/50" in message


class TestSemaphoreDataIntegrity:
    """Tests de integridad de datos y validaciones."""
    
    def test_remaining_never_exceeds_total(self):
        """Test: Restantes nunca debe exceder el total."""
        semaphore = ProcessSemaphore()
        
        # Caso donde los contadores no suman correctamente
        status = {
            "total_projects": 50,
            "processed_count": 0,
            "failed_count": 0,
            "not_found_count": 0
        }
        
        remaining = semaphore.calculate_remaining_projects(status)
        assert remaining <= status["total_projects"]
    
    def test_counters_sum_logic(self):
        """Test: Suma de contadores."""
        semaphore = ProcessSemaphore()
        
        total = 100
        processed = 60
        failed = 20
        not_found = 15
        
        status = {
            "total_projects": total,
            "processed_count": processed,
            "failed_count": failed,
            "not_found_count": not_found
        }
        
        remaining = semaphore.calculate_remaining_projects(status)
        
        # Verificar que la suma es correcta
        assert remaining == (total - processed - failed - not_found)
        assert processed + failed + not_found + remaining == total


class TestSemaphoreMessageContent:
    """Tests del contenido específico de mensajes."""
    
    def test_message_contains_all_emojis(self):
        """Test: Mensaje contiene todos los emojis esperados."""
        semaphore = ProcessSemaphore()
        
        status = {
            "is_locked": True,
            "locked_at": datetime.now(timezone.utc),
            "last_activity_at": datetime.now(timezone.utc),
            "total_projects": 50,
            "processed_count": 30,
            "failed_count": 5,
            "not_found_count": 3
        }
        
        message = semaphore.format_telemetry_message(status)
        
        # Verificar emojis específicos
        assert "🔒" in message  # Bloqueado
        assert "📅" in message  # Fecha
        assert "⏱️" in message  # Tiempo
        assert "📊" in message  # Proyectos
        assert "✅" in message  # Procesados
        assert "❌" in message  # Fallidos
        assert "🚫" in message  # No encontrados
    
    def test_message_structure_multiline(self):
        """Test: Mensaje tiene estructura de múltiples líneas."""
        semaphore = ProcessSemaphore()
        
        status = {
            "is_locked": True,
            "locked_at": datetime.now(timezone.utc),
            "last_activity_at": datetime.now(timezone.utc),
            "total_projects": 50,
            "processed_count": 30,
            "failed_count": 5,
            "not_found_count": 3
        }
        
        message = semaphore.format_telemetry_message(status)
        
        lines = message.split('\n')
        assert len(lines) >= 7, "Mensaje debería tener al menos 7 líneas"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
