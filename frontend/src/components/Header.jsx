import { useMemo } from "react";

export default function Header({ userName, onLogout }) {
  const saudacao = useMemo(() => `Bem-vindo, ${userName || "Operador"}`, [userName]);

  return (
    <header className="mb-5 flex items-center justify-between gap-3">
      <div>
        <p className="text-xs uppercase tracking-[0.2em] text-amber-300">SysPetro</p>
        <h1 className="font-heading text-2xl md:text-3xl">{saudacao}</h1>
      </div>
      <button
        className="rounded-xl border border-white/20 px-4 py-2 text-sm font-semibold text-white transition hover:bg-white/10"
        onClick={onLogout}
      >
        Sair
      </button>
    </header>
  );
}
