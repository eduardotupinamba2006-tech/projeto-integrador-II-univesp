// Cliente do Supabase no navegador. A URL e a chave publicável vêm de /api/config,
// que lê as variáveis de ambiente do deploy (preview e produção usam projetos diferentes).
import { createClient } from 'https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.117.2/+esm';

const resposta = await fetch('/api/config');
if (!resposta.ok) throw new Error('Não foi possível carregar a configuração do site.');

export const config = await resposta.json();
export const supabase = createClient(config.supabaseUrl, config.supabaseKey);
