from kicad_ia.kicad.backups import plugin_backup_dir, plugin_temp_dir


def test_plugin_backup_dir_nests_under_project_backup(tmp_path):
    project = tmp_path / "placa-demo"
    project.mkdir()
    path = plugin_backup_dir(project)
    assert path == project / "placa-demo-backups" / "kicad-ia"
    assert path.is_dir()
    assert (path / ".gitignore").read_text(encoding="utf-8") == "*\n"
    # No ensucia la raíz del proyecto.
    assert not (project / ".kicad-ia-backups").exists()


def test_plugin_temp_dir_stays_inside_plugin_backup(tmp_path):
    project = tmp_path / "placa-demo"
    project.mkdir()
    work = plugin_temp_dir(project, "kicad-ia-route-", "placa-demo")
    assert work.is_dir()
    assert work.parent == project / "placa-demo-backups" / "kicad-ia"
    assert work.name.startswith("kicad-ia-route-")
    assert not any(project.glob("kicad-ia-route-*"))
