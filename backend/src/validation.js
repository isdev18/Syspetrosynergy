import { z } from "zod";

export const loginSchema = z.object({
  login: z.string().min(1),
  senha: z.string().min(1),
});

export const medicaoSchema = z.object({
  campo_id: z.string().min(1),
  tanque_id: z.string().min(1),
  hora: z.string().min(1),
  medida: z.coerce.number().finite(),
  situacao: z.enum(["Normal", "Atencao", "Critico", "Manutencao", "Parado"]),
  observacao: z.string().optional().default(""),
});
