import express from "express";
import bcrypt from "bcryptjs";
import users from "../data/users.json" with { type: "json" };
import { loginSchema } from "../validation.js";
import { signToken } from "../middleware/auth.js";

const router = express.Router();

function getConfiguredUser() {
  const login = process.env.DEFAULT_USER_LOGIN || users[0]?.login;
  const name = process.env.DEFAULT_USER_NAME || users[0]?.name || "Operador";
  const passwordHash = process.env.DEFAULT_USER_PASSWORD_HASH;

  if (!passwordHash) {
    return null;
  }

  return {
    id: "env-user",
    login,
    name,
    role: "operator",
    passwordHash,
  };
}

router.post("/login", (req, res) => {
  const parsed = loginSchema.safeParse(req.body);
  if (!parsed.success) {
    return res.status(400).json({ message: "Dados invalidos" });
  }

  const configuredUser = getConfiguredUser();
  if (!configuredUser) {
    return res.status(500).json({
      message: "Configure DEFAULT_USER_PASSWORD_HASH no .env antes de usar o login",
    });
  }

  const { login, senha } = parsed.data;
  if (login !== configuredUser.login) {
    return res.status(401).json({ message: "Login ou senha invalidos" });
  }

  const ok = bcrypt.compareSync(senha, configuredUser.passwordHash);
  if (!ok) {
    return res.status(401).json({ message: "Login ou senha invalidos" });
  }

  const token = signToken(configuredUser);
  return res.json({ token, user: { name: configuredUser.name, role: configuredUser.role } });
});

router.post("/logout", (_req, res) => {
  return res.json({ message: "Logout realizado" });
});

export default router;

