import dotenv from "dotenv";
import express from "express";
import cors from "cors";
import cookieParser from "cookie-parser";

import authRoutes from "./routes/auth.js";
import catalogRoutes from "./routes/catalog.js";
import medicoesRoutes from "./routes/medicoes.js";

dotenv.config();

const app = express();
const port = process.env.PORT || 4000;

app.use(
  cors({
    origin: process.env.FRONTEND_URL || "http://localhost:5173",
    credentials: true,
  })
);
app.use(express.json());
app.use(cookieParser());

app.get("/health", (_req, res) => {
  res.json({ status: "ok", service: "SysPetro API" });
});

app.use("/auth", authRoutes);
app.use(catalogRoutes);
app.use(medicoesRoutes);

app.use((err, _req, res, _next) => {
  console.error("Erro nao tratado:", err);
  res.status(500).json({ message: "Erro interno" });
});

app.listen(port, () => {
  console.log(`SysPetro API rodando na porta ${port}`);
});
