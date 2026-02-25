import bcrypt from "bcryptjs";

const password = process.argv[2];
if (!password) {
  console.error("Use: npm run hash:password -- \"sua-senha\"");
  process.exit(1);
}

const hash = bcrypt.hashSync(password, 10);
console.log(hash);
