const SITUACOES = ["Normal", "Atencao", "Critico", "Manutencao", "Parado"];

export default function MedicaoForm({
  campos,
  tanques,
  form,
  onChange,
  onSubmit,
  loading,
  message,
}) {
  return (
    <div className="card w-full">
      <h2 className="font-heading text-2xl">Nova Medicao</h2>
      <p className="mt-1 text-sm text-slate-300">Preencha e envie para a planilha correta do tanque.</p>

      <form className="mt-4 grid gap-3" onSubmit={onSubmit}>
        <select
          className="input-base"
          value={form.campo_id}
          onChange={(e) => onChange("campo_id", e.target.value)}
          required
        >
          <option value="">Selecione o campo</option>
          {campos.map((c) => (
            <option key={c.campo_id} value={c.campo_id}>{c.campo_nome}</option>
          ))}
        </select>

        <select
          className="input-base"
          value={form.tanque_id}
          onChange={(e) => onChange("tanque_id", e.target.value)}
          required
          disabled={!form.campo_id}
        >
          <option value="">Selecione o tanque</option>
          {tanques.map((t) => (
            <option key={t.tanque_id} value={t.tanque_id}>{t.tanque_nome}</option>
          ))}
        </select>

        <input
          className="input-base"
          type="time"
          value={form.hora}
          onChange={(e) => onChange("hora", e.target.value)}
          required
        />

        <input
          className="input-base"
          type="number"
          step="0.01"
          placeholder="Medida (ex: 12345.67)"
          value={form.medida}
          onChange={(e) => onChange("medida", e.target.value)}
          required
        />

        <select
          className="input-base"
          value={form.situacao}
          onChange={(e) => onChange("situacao", e.target.value)}
          required
        >
          {SITUACOES.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>

        <textarea
          className="input-base min-h-24"
          placeholder="Observacao (opcional)"
          value={form.observacao}
          onChange={(e) => onChange("observacao", e.target.value)}
        />

        {message ? <p className="text-sm text-emerald-300">{message}</p> : null}
        <button className="btn-primary" type="submit" disabled={loading}>
          {loading ? "Salvando..." : "Salvar Medicao"}
        </button>
      </form>
    </div>
  );
}
