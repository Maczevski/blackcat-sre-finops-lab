package app.config;

import io.jsonwebtoken.SignatureAlgorithm;

public class JwtConfig {

    // Parâmetros para geração do token JWT (Higienizado com placeholder)
    public static final String SECRET_KEY = "<JWT_SECRET_KEY_256_BITS>";
    public static final SignatureAlgorithm ALGORITMO_ASSINATURA = SignatureAlgorithm.HS256;
    public static final int HORAS_EXPIRACAO_TOKEN = 1;

}
