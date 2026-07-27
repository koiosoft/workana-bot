collected 69 items                                                                                                                                    

tests/test_init_command.py ........                                                                                                             [ 11%]
tests/test_instructor.py .....................F............................                                                                     [ 84%]
tests/test_validation_flow.py ...........                                                                                                       [100%]

====================================================================== FAILURES =======================================================================
__________________________________________________________ test_call_fabric_writes_log_file ___________________________________________________________

temp_root_dir = PosixPath('/private/var/folders/t_/lb5dg1gn7bv513tl4mk572bc0000gp/T/pytest-of-rzavala/pytest-2/test_call_fabric_writes_log_fi0')

    def test_call_fabric_writes_log_file(temp_root_dir: Path) -> None:
        """Should write a log file with model info, system prompt and payload."""
        pattern_dir = Path.home() / ".config/fabric/patterns/agent_instructor"
        pattern_dir.mkdir(parents=True, exist_ok=True)
        (pattern_dir / "system.md").write_text("placeholder", encoding="utf-8")
    
        with mock.patch("instructor.subprocess.Popen") as mock_popen:
            mock_popen.return_value.communicate.return_value = ("output", "")
            mock_popen.return_value.returncode = 0
    
            with mock.patch.object(instructor, "get_fabric_model_info", return_value="TestVendor / TestModel"):
                with mock.patch.object(instructor, "ROOT_DIR", temp_root_dir):
                    instructor.call_fabric("SYSTEM", "PAYLOAD", "INSTRUCTIONS.md")
    
            log_dir = temp_root_dir / ".sdd/logs/instruction-generation"
            log_files = list(log_dir.glob("fabric_payload_*.log"))
            log_files = list(log_dir.glob("fabric_payload_*.log"))
>           assert len(log_files) >= 1  # at least one file; test may have created others
            ^^^^^^^^^^^^^^^^^^^^^^^^^^
E           assert 0 >= 1
E            +  where 0 = len([])

tests/test_instructor.py:370: AssertionError
---------------------------------------------------------------- Captured stdout call -----------------------------------------------------------------
🤖 Fabric AI Model: TestVendor / TestModel
📝 Contexto guardado en: /private/var/folders/t_/lb5dg1gn7bv513tl4mk572bc0000gp/T/pytest-of-rzavala/pytest-2/test_call_fabric_writes_log_fi0/.sdd/logs/fabric/fabric_payload_20260721_125041.log
📝 Generando INSTRUCTIONS.md  ...
=============================================================== short test summary info ===============================================================
FAILED tests/test_instructor.py::test_call_fabric_writes_log_file - assert 0 >= 1
============================================================ 1 failed, 68 passed in 3.04s =========================================================