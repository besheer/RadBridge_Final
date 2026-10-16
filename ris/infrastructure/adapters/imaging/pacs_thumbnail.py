"""Bounded retrieval of actual study previews; never fabricate image pixels."""


class ThumbnailUnavailable(Exception):
    pass


def study_preview(study, get_series, get_preview):
    def candidates():
        for instance in (study.get('Instances') or [])[:4]:
            yield instance
        for series_id in (study.get('Series') or [])[:8]:
            try:
                series = get_series(series_id)
            except Exception:
                continue
            if str((series.get('MainDicomTags') or {}).get('Modality') or '').upper() in {'SR', 'PR', 'KO', 'DOC'}:
                continue
            for instance in (series.get('Instances') or [])[:4]:
                yield instance

    attempted = set()
    for instance in candidates():
        instance = str(instance or '').strip()
        if not instance or instance in attempted:
            continue
        attempted.add(instance)
        try:
            response = get_preview(instance)
            response.raise_for_status()
            mime = (response.headers.get('Content-Type') or '').split(';', 1)[0].strip().lower()
            data = response.content
            if (mime == 'image/png' and data.startswith(b'\x89PNG\r\n\x1a\n')) or (
                mime == 'image/jpeg' and data.startswith(b'\xff\xd8\xff')
            ):
                return data, mime
        except Exception:
            pass
        if len(attempted) >= 4:
            break
    raise ThumbnailUnavailable('No usable PACS pixel preview within the lookup limit')
