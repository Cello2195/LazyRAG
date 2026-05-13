from pathlib import Path

from chat.components.lclm import artifact as lclm_artifact


def test_save_longform_artifact_uses_existing_save_artifact(monkeypatch, tmp_path):
    calls = {}

    def fake_artifact_dir(kind: str):
        calls['kind'] = kind
        out = tmp_path / kind
        out.mkdir(parents=True, exist_ok=True)
        return out

    def fake_save_artifact(file_path, kind='pptx', filename=None, related_artifacts=None):
        path = Path(file_path)
        calls['saved_kind'] = kind
        calls['saved_filename'] = filename
        calls['saved_path'] = str(path)
        calls['related'] = related_artifacts
        return {
            'success': True,
            'file_path': str(path),
            'download_url': 'https://example.com/download',
            'download_link': 'https://example.com/download?sig=abc',
            'artifact': {
                'download_url': 'https://example.com/download',
                'download_link': 'https://example.com/download?sig=abc',
            },
        }

    monkeypatch.setattr(lclm_artifact, 'artifact_dir', fake_artifact_dir)
    monkeypatch.setattr(lclm_artifact, 'save_artifact', fake_save_artifact)

    result = lclm_artifact.save_longform_artifact(
        content='# 标题\n正文',
        title='测试报告',
        output_format='markdown',
        related_artifacts={'outline': []},
    )

    assert result['success'] is True
    assert result['download_url'] == 'https://example.com/download'
    assert result['download_link'] == 'https://example.com/download?sig=abc'
    assert calls['kind'] == 'lclm-longform-work'
    assert calls['saved_kind'] == 'lclm-longform'
    assert calls['saved_filename'].endswith('.md')
    assert Path(calls['saved_path']).exists()
