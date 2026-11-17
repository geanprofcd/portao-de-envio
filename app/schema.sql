-- Portão de envio: uma reserva por mensagem, recusas e histórico de falhas.

create table if not exists recusas (
    telefone   text primary key,
    motivo     text,
    criado_em  timestamptz not null default now()
);

create table if not exists envios (
    id             bigserial primary key,
    telefone       text not null,
    origem         text not null,
    chave          text not null,
    status         text not null check (status in ('reservado', 'enviado', 'falhou')),
    erro           text,
    criado_em      timestamptz not null default now(),
    atualizado_em  timestamptz not null default now()
);

-- A mesma chave de idempotência nunca gera duas reservas, mesmo que a automação repita a chamada.
create unique index if not exists envios_chave_unica on envios (chave);
create index if not exists envios_telefone_data on envios (telefone, criado_em desc);
create index if not exists envios_falhas_recentes on envios (atualizado_em) where status = 'falhou';
