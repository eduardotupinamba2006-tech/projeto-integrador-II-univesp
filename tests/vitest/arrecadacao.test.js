import { describe, expect, it } from 'vitest';
import {
  arrecadacaoPorMes, arrecadacaoPorParoquia, contarSolicitacoes, somarArrecadacao,
} from '../../js/lib/arrecadacao.js';

const pagamentos = [
  { paroquia_id: 'a1', tipo: 'dizimo', status: 'pago', valor: '150.10', criado_em: '2026-08-10T10:00:00Z' },
  { paroquia_id: 'a1', tipo: 'dizimo', status: 'pago', valor: '0.20', criado_em: '2026-09-01T10:00:00Z' },
  { paroquia_id: 'a1', tipo: 'taxa_certidao', status: 'pago', valor: '30', criado_em: '2026-09-02T10:00:00Z' },
  { paroquia_id: 'a1', tipo: 'dizimo', status: 'pendente', valor: '999', criado_em: '2026-09-03T10:00:00Z' },
  { paroquia_id: 'a2', tipo: 'dizimo', status: 'estornado', valor: '500', criado_em: '2026-09-04T10:00:00Z' },
  { paroquia_id: 'a2', tipo: 'dizimo', status: 'pago', valor: '80', criado_em: '2026-09-05T10:00:00Z' },
];

describe('somarArrecadacao', () => {
  it('soma só pagamentos confirmados, separando dízimo e taxa, sem erro de ponto flutuante', () => {
    expect(somarArrecadacao(pagamentos)).toEqual({ dizimo: 230.3, taxa_certidao: 30, total: 260.3 });
  });

  it('lista vazia soma zero', () => {
    expect(somarArrecadacao([])).toEqual({ dizimo: 0, taxa_certidao: 0, total: 0 });
  });
});

describe('arrecadacaoPorParoquia', () => {
  it('agrupa por paróquia em ordem alfabética, incluindo paróquia sem arrecadação', () => {
    const paroquias = [
      { id: 'a2', nome: 'Santa Amostra' },
      { id: 'a1', nome: 'São Exemplo' },
      { id: 'a3', nome: 'Imaculada Fictícia' },
    ];
    const linhas = arrecadacaoPorParoquia(pagamentos, paroquias);
    expect(linhas.map((l) => [l.paroquia.id, l.total])).toEqual([['a3', 0], ['a2', 80], ['a1', 180.3]]);
  });
});

describe('arrecadacaoPorMes', () => {
  it('agrupa por mês em ordem cronológica', () => {
    expect(arrecadacaoPorMes(pagamentos).map((m) => [m.mes, m.total])).toEqual([
      ['2026-08', 150.1],
      ['2026-09', 110.2],
    ]);
  });
});

describe('contarSolicitacoes', () => {
  it('conta por status', () => {
    const c = contarSolicitacoes([{ status: 'aprovado' }, { status: 'aprovado' }, { status: 'em_analise' }]);
    expect(c).toEqual({ total: 3, aguardando_pagamento: 0, em_analise: 1, aprovado: 2, rejeitado: 0 });
  });
});
