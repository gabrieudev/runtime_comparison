-- Criar tabela products se não existir
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    category VARCHAR(100) NOT NULL,
    stock INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Inserir dados de teste se a tabela estiver vazia
DO $$
DECLARE
    row_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO row_count FROM products;
    
    IF row_count = 0 THEN
        INSERT INTO products (name, price, category, stock)
        SELECT
            'Produto ' || generate_series,
            round((random() * 500 + 0.99)::numeric, 2),
            CASE floor(random() * 5)
                WHEN 0 THEN 'Eletrônicos'
                WHEN 1 THEN 'Livros'
                WHEN 2 THEN 'Roupas'
                WHEN 3 THEN 'Casa'
                WHEN 4 THEN 'Esportes'
            END,
            floor(random() * 1000)
        FROM generate_series(1, 10000);
        
        RAISE NOTICE 'Inseridos 10000 produtos de teste';
    ELSE
        RAISE NOTICE 'Tabela já contém % produtos', row_count;
    END IF;
END $$;