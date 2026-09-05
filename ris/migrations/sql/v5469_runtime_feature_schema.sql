--
-- PostgreSQL database dump
--


-- Dumped from database version 16.15
-- Dumped by pg_dump version 16.15




--
-- Name: complaint_ticket; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.complaint_ticket (
    id integer NOT NULL,
    ticket_no character varying(40) NOT NULL,
    patient_id integer,
    call_log_id integer,
    appointment_id integer,
    order_id integer,
    branch_id integer,
    category character varying(50) DEFAULT 'GENERAL'::character varying NOT NULL,
    priority character varying(20) DEFAULT 'NORMAL'::character varying NOT NULL,
    description text NOT NULL,
    status character varying(30) DEFAULT 'OPEN'::character varying NOT NULL,
    assigned_to integer,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    resolved_at timestamp without time zone,
    resolution text DEFAULT ''::text NOT NULL
);


--
-- Name: complaint_ticket_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.complaint_ticket_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: complaint_ticket_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.complaint_ticket_id_seq OWNED BY public.complaint_ticket.id;


--
-- Name: conference_invitation; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.conference_invitation (
    id integer NOT NULL,
    room_id integer,
    token character varying(120) NOT NULL,
    invited_by_user_id integer,
    invited_email character varying(200),
    invited_phone character varying(50),
    expires_at timestamp without time zone,
    used boolean DEFAULT false,
    revoked boolean DEFAULT false,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: conference_invitation_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.conference_invitation_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: conference_invitation_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.conference_invitation_id_seq OWNED BY public.conference_invitation.id;


--
-- Name: conference_room; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.conference_room (
    id integer NOT NULL,
    code character varying(80) NOT NULL,
    name character varying(150) NOT NULL,
    extension character varying(20),
    department character varying(80),
    active boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: conference_room_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.conference_room_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: conference_room_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.conference_room_id_seq OWNED BY public.conference_room.id;


--
-- Name: public_chat_message; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.public_chat_message (
    id bigint NOT NULL,
    session_id bigint NOT NULL,
    sender_type character varying(20) NOT NULL,
    sender_user_id integer,
    message text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: public_chat_message_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.public_chat_message_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: public_chat_message_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.public_chat_message_id_seq OWNED BY public.public_chat_message.id;


--
-- Name: public_chat_session; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.public_chat_session (
    id bigint NOT NULL,
    public_token character varying(80) NOT NULL,
    contact_request_id bigint,
    state character varying(30) DEFAULT 'BOT'::character varying NOT NULL,
    assigned_user_id integer,
    bot_failures integer DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    closed_at timestamp with time zone
);


--
-- Name: public_chat_session_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.public_chat_session_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: public_chat_session_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.public_chat_session_id_seq OWNED BY public.public_chat_session.id;


--
-- Name: public_contact_attachment; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.public_contact_attachment (
    id bigint NOT NULL,
    contact_request_id bigint NOT NULL,
    attachment_type character varying(50) DEFAULT 'OTHER'::character varying NOT NULL,
    description character varying(300),
    original_filename character varying(300) NOT NULL,
    stored_filename character varying(300) NOT NULL,
    mime_type character varying(120),
    size_bytes bigint DEFAULT 0 NOT NULL,
    verification_status character varying(30) DEFAULT 'PENDING'::character varying NOT NULL,
    verified_by_user_id integer,
    verified_at timestamp with time zone,
    rejected_by_user_id integer,
    rejected_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: public_contact_attachment_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.public_contact_attachment_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: public_contact_attachment_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.public_contact_attachment_id_seq OWNED BY public.public_contact_attachment.id;


--
-- Name: public_contact_request; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.public_contact_request (
    id bigint NOT NULL,
    reference character varying(40) NOT NULL,
    patient_name character varying(160),
    phone character varying(40),
    booking_reference character varying(100),
    request_type character varying(40) DEFAULT 'OTHER'::character varying NOT NULL,
    message text,
    status character varying(30) DEFAULT 'NEW'::character varying NOT NULL,
    source character varying(30) DEFAULT 'WEB'::character varying NOT NULL,
    assigned_user_id integer,
    confirmed boolean DEFAULT false NOT NULL,
    confirmed_by_user_id integer,
    confirmed_at timestamp with time zone,
    rejected_by_user_id integer,
    rejected_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    date_of_birth date,
    age_years integer,
    exam_name character varying(240),
    insurance_company character varying(200),
    insurance_member_no character varying(120),
    medical_approval_no character varying(160),
    medical_approval_status character varying(40) DEFAULT 'NOT_DECLARED'::character varying,
    notification_whatsapp boolean DEFAULT false NOT NULL,
    notification_sms boolean DEFAULT false NOT NULL,
    notification_email boolean DEFAULT false NOT NULL,
    notification_web_chat boolean DEFAULT true NOT NULL,
    notification_email_address character varying(240),
    payment_preference character varying(50),
    appointment_status character varying(40) DEFAULT 'NOT_REQUESTED'::character varying NOT NULL,
    requested_branch_id integer,
    requested_procedure_id integer,
    requested_date date,
    requested_time time without time zone
);


--
-- Name: public_contact_request_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.public_contact_request_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: public_contact_request_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.public_contact_request_id_seq OWNED BY public.public_contact_request.id;


--
-- Name: telephony_agent_state; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.telephony_agent_state (
    id integer NOT NULL,
    user_id integer,
    extension character varying(30) NOT NULL,
    status character varying(20) DEFAULT 'OFFLINE'::character varying NOT NULL,
    current_call_id character varying(100),
    last_seen timestamp without time zone,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: telephony_agent_state_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.telephony_agent_state_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: telephony_agent_state_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.telephony_agent_state_id_seq OWNED BY public.telephony_agent_state.id;


--
-- Name: voice_caller_control; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.voice_caller_control (
    id bigint NOT NULL,
    phone character varying(40) NOT NULL,
    status character varying(30) DEFAULT 'NORMAL'::character varying NOT NULL,
    reason character varying(160),
    notes text,
    call_count integer DEFAULT 0 NOT NULL,
    last_call_at timestamp without time zone,
    blocked_by integer,
    blocked_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


--
-- Name: voice_caller_control_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.voice_caller_control_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: voice_caller_control_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.voice_caller_control_id_seq OWNED BY public.voice_caller_control.id;


--
-- Name: voice_intake_review; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.voice_intake_review (
    id bigint NOT NULL,
    reference character varying(40) NOT NULL,
    branch_id integer,
    patient_id integer,
    appointment_id integer,
    source character varying(30) DEFAULT 'VOICE_AI'::character varying NOT NULL,
    reason character varying(80) DEFAULT 'AI_UNCLEAR_DATA'::character varying NOT NULL,
    status character varying(30) DEFAULT 'PENDING'::character varying NOT NULL,
    phone_text character varying(100),
    patient_name_text character varying(200),
    procedure_text character varying(250),
    notes text,
    transcript text,
    audio_path character varying(500),
    audio_mime character varying(100),
    reviewed_by integer,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    reviewed_at timestamp without time zone,
    converted_at timestamp without time zone,
    caller_phone character varying(40),
    audio_deleted_at timestamp without time zone,
    spam_flag boolean DEFAULT false NOT NULL,
    spam_reason character varying(160)
);


--
-- Name: voice_intake_review_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.voice_intake_review_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: voice_intake_review_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.voice_intake_review_id_seq OWNED BY public.voice_intake_review.id;


--
-- Name: voice_storage_settings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.voice_storage_settings (
    id integer NOT NULL,
    retention_days integer DEFAULT 30 NOT NULL,
    spam_retention_days integer DEFAULT 7 NOT NULL,
    auto_cleanup_enabled boolean DEFAULT true NOT NULL,
    warn_percent integer DEFAULT 80 NOT NULL,
    critical_percent integer DEFAULT 90 NOT NULL,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


--
-- Name: complaint_ticket id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.complaint_ticket ALTER COLUMN id SET DEFAULT nextval('public.complaint_ticket_id_seq'::regclass);


--
-- Name: conference_invitation id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conference_invitation ALTER COLUMN id SET DEFAULT nextval('public.conference_invitation_id_seq'::regclass);


--
-- Name: conference_room id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conference_room ALTER COLUMN id SET DEFAULT nextval('public.conference_room_id_seq'::regclass);


--
-- Name: public_chat_message id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.public_chat_message ALTER COLUMN id SET DEFAULT nextval('public.public_chat_message_id_seq'::regclass);


--
-- Name: public_chat_session id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.public_chat_session ALTER COLUMN id SET DEFAULT nextval('public.public_chat_session_id_seq'::regclass);


--
-- Name: public_contact_attachment id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.public_contact_attachment ALTER COLUMN id SET DEFAULT nextval('public.public_contact_attachment_id_seq'::regclass);


--
-- Name: public_contact_request id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.public_contact_request ALTER COLUMN id SET DEFAULT nextval('public.public_contact_request_id_seq'::regclass);


--
-- Name: telephony_agent_state id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.telephony_agent_state ALTER COLUMN id SET DEFAULT nextval('public.telephony_agent_state_id_seq'::regclass);


--
-- Name: voice_caller_control id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.voice_caller_control ALTER COLUMN id SET DEFAULT nextval('public.voice_caller_control_id_seq'::regclass);


--
-- Name: voice_intake_review id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.voice_intake_review ALTER COLUMN id SET DEFAULT nextval('public.voice_intake_review_id_seq'::regclass);


--
-- Name: complaint_ticket complaint_ticket_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.complaint_ticket
    ADD CONSTRAINT complaint_ticket_pkey PRIMARY KEY (id);


--
-- Name: complaint_ticket complaint_ticket_ticket_no_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.complaint_ticket
    ADD CONSTRAINT complaint_ticket_ticket_no_key UNIQUE (ticket_no);


--
-- Name: conference_invitation conference_invitation_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conference_invitation
    ADD CONSTRAINT conference_invitation_pkey PRIMARY KEY (id);


--
-- Name: conference_invitation conference_invitation_token_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conference_invitation
    ADD CONSTRAINT conference_invitation_token_key UNIQUE (token);


--
-- Name: conference_room conference_room_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conference_room
    ADD CONSTRAINT conference_room_code_key UNIQUE (code);


--
-- Name: conference_room conference_room_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conference_room
    ADD CONSTRAINT conference_room_pkey PRIMARY KEY (id);


--
-- Name: public_chat_message public_chat_message_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.public_chat_message
    ADD CONSTRAINT public_chat_message_pkey PRIMARY KEY (id);


--
-- Name: public_chat_session public_chat_session_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.public_chat_session
    ADD CONSTRAINT public_chat_session_pkey PRIMARY KEY (id);


--
-- Name: public_chat_session public_chat_session_public_token_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.public_chat_session
    ADD CONSTRAINT public_chat_session_public_token_key UNIQUE (public_token);


--
-- Name: public_contact_attachment public_contact_attachment_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.public_contact_attachment
    ADD CONSTRAINT public_contact_attachment_pkey PRIMARY KEY (id);


--
-- Name: public_contact_request public_contact_request_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.public_contact_request
    ADD CONSTRAINT public_contact_request_pkey PRIMARY KEY (id);


--
-- Name: public_contact_request public_contact_request_reference_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.public_contact_request
    ADD CONSTRAINT public_contact_request_reference_key UNIQUE (reference);


--
-- Name: telephony_agent_state telephony_agent_state_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.telephony_agent_state
    ADD CONSTRAINT telephony_agent_state_pkey PRIMARY KEY (id);


--
-- Name: telephony_agent_state telephony_agent_state_user_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.telephony_agent_state
    ADD CONSTRAINT telephony_agent_state_user_id_key UNIQUE (user_id);


--
-- Name: voice_caller_control voice_caller_control_phone_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.voice_caller_control
    ADD CONSTRAINT voice_caller_control_phone_key UNIQUE (phone);


--
-- Name: voice_caller_control voice_caller_control_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.voice_caller_control
    ADD CONSTRAINT voice_caller_control_pkey PRIMARY KEY (id);


--
-- Name: voice_intake_review voice_intake_review_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.voice_intake_review
    ADD CONSTRAINT voice_intake_review_pkey PRIMARY KEY (id);


--
-- Name: voice_intake_review voice_intake_review_reference_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.voice_intake_review
    ADD CONSTRAINT voice_intake_review_reference_key UNIQUE (reference);


--
-- Name: voice_storage_settings voice_storage_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.voice_storage_settings
    ADD CONSTRAINT voice_storage_settings_pkey PRIMARY KEY (id);


--
-- Name: idx_voice_caller_last_call; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_voice_caller_last_call ON public.voice_caller_control USING btree (last_call_at);


--
-- Name: idx_voice_caller_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_voice_caller_status ON public.voice_caller_control USING btree (status);


--
-- Name: idx_voice_intake_branch; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_voice_intake_branch ON public.voice_intake_review USING btree (branch_id);


--
-- Name: idx_voice_intake_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_voice_intake_created ON public.voice_intake_review USING btree (created_at DESC);


--
-- Name: idx_voice_intake_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_voice_intake_status ON public.voice_intake_review USING btree (status);


--
-- Name: ix_complaint_ticket_call; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_complaint_ticket_call ON public.complaint_ticket USING btree (call_log_id);


--
-- Name: ix_complaint_ticket_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_complaint_ticket_created ON public.complaint_ticket USING btree (created_at);


--
-- Name: ix_complaint_ticket_patient; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_complaint_ticket_patient ON public.complaint_ticket USING btree (patient_id);


--
-- Name: ix_complaint_ticket_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_complaint_ticket_status ON public.complaint_ticket USING btree (status);


--
-- Name: ix_public_chat_message_session; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_public_chat_message_session ON public.public_chat_message USING btree (session_id, id);


--
-- Name: ix_public_chat_session_state; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_public_chat_session_state ON public.public_chat_session USING btree (state);


--
-- Name: ix_public_contact_attachment_request; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_public_contact_attachment_request ON public.public_contact_attachment USING btree (contact_request_id);


--
-- Name: ix_public_contact_request_phone; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_public_contact_request_phone ON public.public_contact_request USING btree (phone);


--
-- Name: ix_public_contact_request_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_public_contact_request_status ON public.public_contact_request USING btree (status);


--
-- Name: complaint_ticket complaint_ticket_appointment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.complaint_ticket
    ADD CONSTRAINT complaint_ticket_appointment_id_fkey FOREIGN KEY (appointment_id) REFERENCES public.appointment(id) ON DELETE SET NULL;


--
-- Name: complaint_ticket complaint_ticket_assigned_to_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.complaint_ticket
    ADD CONSTRAINT complaint_ticket_assigned_to_fkey FOREIGN KEY (assigned_to) REFERENCES public."user"(id) ON DELETE SET NULL;


--
-- Name: complaint_ticket complaint_ticket_branch_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.complaint_ticket
    ADD CONSTRAINT complaint_ticket_branch_id_fkey FOREIGN KEY (branch_id) REFERENCES public.branch(id) ON DELETE SET NULL;


--
-- Name: complaint_ticket complaint_ticket_call_log_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.complaint_ticket
    ADD CONSTRAINT complaint_ticket_call_log_id_fkey FOREIGN KEY (call_log_id) REFERENCES public.call_log(id) ON DELETE SET NULL;


--
-- Name: complaint_ticket complaint_ticket_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.complaint_ticket
    ADD CONSTRAINT complaint_ticket_order_id_fkey FOREIGN KEY (order_id) REFERENCES public."order"(id) ON DELETE SET NULL;


--
-- Name: complaint_ticket complaint_ticket_patient_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.complaint_ticket
    ADD CONSTRAINT complaint_ticket_patient_id_fkey FOREIGN KEY (patient_id) REFERENCES public.patient(id) ON DELETE SET NULL;


--
-- Name: conference_invitation conference_invitation_room_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conference_invitation
    ADD CONSTRAINT conference_invitation_room_id_fkey FOREIGN KEY (room_id) REFERENCES public.conference_room(id);


--
-- Name: public_chat_message public_chat_message_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.public_chat_message
    ADD CONSTRAINT public_chat_message_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.public_chat_session(id) ON DELETE CASCADE;


--
-- Name: public_chat_session public_chat_session_contact_request_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.public_chat_session
    ADD CONSTRAINT public_chat_session_contact_request_id_fkey FOREIGN KEY (contact_request_id) REFERENCES public.public_contact_request(id) ON DELETE CASCADE;


--
-- Name: public_contact_attachment public_contact_attachment_contact_request_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.public_contact_attachment
    ADD CONSTRAINT public_contact_attachment_contact_request_id_fkey FOREIGN KEY (contact_request_id) REFERENCES public.public_contact_request(id) ON DELETE CASCADE;


--
-- Name: voice_caller_control voice_caller_control_blocked_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.voice_caller_control
    ADD CONSTRAINT voice_caller_control_blocked_by_fkey FOREIGN KEY (blocked_by) REFERENCES public."user"(id) ON DELETE SET NULL;


--
-- Name: voice_intake_review voice_intake_review_appointment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.voice_intake_review
    ADD CONSTRAINT voice_intake_review_appointment_id_fkey FOREIGN KEY (appointment_id) REFERENCES public.appointment(id) ON DELETE SET NULL;


--
-- Name: voice_intake_review voice_intake_review_branch_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.voice_intake_review
    ADD CONSTRAINT voice_intake_review_branch_id_fkey FOREIGN KEY (branch_id) REFERENCES public.branch(id) ON DELETE SET NULL;


--
-- Name: voice_intake_review voice_intake_review_patient_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.voice_intake_review
    ADD CONSTRAINT voice_intake_review_patient_id_fkey FOREIGN KEY (patient_id) REFERENCES public.patient(id) ON DELETE SET NULL;


--
-- Name: voice_intake_review voice_intake_review_reviewed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.voice_intake_review
    ADD CONSTRAINT voice_intake_review_reviewed_by_fkey FOREIGN KEY (reviewed_by) REFERENCES public."user"(id) ON DELETE SET NULL;


--
-- PostgreSQL database dump complete
--
