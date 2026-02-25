import { useState } from "react";

export default function LoginForm({ onLogin, loading, error }) {
  const [login, setLogin] = useState("");
  const [senha, setSenha] = useState("");

  const submit = (e) => {
    e.preventDefault();
    onLogin({ login, senha });
  };

  return (
    <div className="card mx-auto mt-10 w-full max-w-md">
      <p className="mb-1 text-sm uppercase tracking-widest text-amber-300">SysPetro</p>
      <h1 className="font-heading text-3xl">Acesso do Operador</h1>
      <p className="mt-2 text-sm text-slate-300">Entre para registrar medicoes de tanques.</p>

      <form onSubmit={submit} className="mt-6 space-y-3">
        <input
          className="input-base"
          placeholder="Email ou matricula"
          value={login}
          onChange={(e) => setLogin(e.target.value)}
          required
        />
        <input
          className="input-base"
          type="password"
          placeholder="Senha"
          value={senha}
          onChange={(e) => setSenha(e.target.value)}
          required
        />
        {error ? <p className="text-sm text-red-300">{error}</p> : null}
        <button className="btn-primary" type="submit" disabled={loading}>
          {loading ? "Entrando..." : "Entrar"}
        </button>
      </form>
    </div>
  );
}
