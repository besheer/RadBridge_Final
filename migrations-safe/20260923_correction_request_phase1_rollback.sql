-- Safety-first rollback. This intentionally refuses to discard request/audit workflow data.
DO $$
DECLARE
    n BIGINT;
BEGIN
    IF to_regclass('public.correction_request') IS NULL THEN
        RETURN;
    END IF;

    SELECT COUNT(*) INTO n FROM correction_request;
    IF n <> 0 THEN
        RAISE EXCEPTION 'ROLLBACK_REFUSED: correction_request contains % row(s); preserve/archive data before schema removal', n;
    END IF;
END $$;

DROP TABLE IF EXISTS correction_request;
