// Formatação de valores, datas e rótulos para exibição.

const moeda = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });

export function formatarMoeda(valor) {
  return moeda.format(Number(valor || 0)).replace(/ /g, ' ');
}

// "1995-03-12" -> "12/03/1995" sem conversão de fuso (datas de sacramento não têm hora).
export function formatarData(iso) {
  if (!iso) return '';
  const [ano, mes, dia] = String(iso).slice(0, 10).split('-');
  return `${dia}/${mes}/${ano}`;
}

export function formatarDataHora(iso) {
  if (!iso) return '';
  return new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' });
}

export const SACRAMENTOS = {
  batismo: 'Batismo',
  primeira_comunhao: 'Primeira Comunhão',
  crisma: 'Crisma',
  casamento: 'Casamento',
  ordenacao: 'Ordenação',
};

export const STATUS_SOLICITACAO = {
  aguardando_pagamento: 'Aguardando pagamento',
  em_analise: 'Em análise pela paróquia',
  aprovado: 'Aprovada',
  rejeitado: 'Não localizada',
};

export const STATUS_PAGAMENTO = {
  pendente: 'Pendente',
  pago: 'Pago',
  estornado: 'Estornado',
};

export function escaparHtml(texto) {
  return String(texto ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
