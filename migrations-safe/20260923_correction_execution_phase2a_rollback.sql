DO $$
DECLARE
    n BIGINT;
BEGIN

    IF to_regclass(
        'public.correction_execution'
    ) IS NULL THEN
        RETURN;
    END IF;

    SELECT COUNT(*)
    INTO n
    FROM correction_execution;

    IF n <> 0 THEN
        RAISE EXCEPTION
          'ROLLBACK_REFUSED: correction_execution contains % row(s); preserve/archive execution history before schema removal',
          n;
    END IF;

END
$$;

DROP TABLE IF EXISTS correction_execution;
