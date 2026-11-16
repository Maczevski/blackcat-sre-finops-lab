package app.Entity;

import com.fasterxml.jackson.annotation.JsonIgnore;
import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.OneToMany;
import jakarta.persistence.Table;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;
import java.util.List;

@Entity
@Table(name = "produto")
public class Produto {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private long id;

    @NotEmpty(message = "O nome do produto é obrigatório")
    private String nome;

    private String descricao;

    private boolean ativo;

    @NotNull(message = "O preço do produto é obrigatório")
    @Positive(message = "O preço deve ser um valor positivo")
    private double preco;

    @OneToMany(mappedBy = "produto")
    @JsonIgnoreProperties({"produto"})
    @JsonIgnore
    private List<ProdutoVenda> produtosVenda;

    public Produto() {
    }

    public Produto(Long id, String nome, String descricao, double preco, boolean ativo) {
        this.id = id != null ? id.longValue() : 0L;
        this.nome = nome;
        this.descricao = descricao;
        this.preco = preco;
        this.ativo = ativo;
    }

    public Produto(long id, String nome, String descricao, boolean ativo, double preco, List<ProdutoVenda> produtosVenda) {
        this.id = id;
        this.nome = nome;
        this.descricao = descricao;
        this.ativo = ativo;
        this.preco = preco;
        this.produtosVenda = produtosVenda;
    }

    public long getId() {
        return this.id;
    }

    public void setId(long id) {
        this.id = id;
    }

    public String getNome() {
        return this.nome;
    }

    public void setNome(String nome) {
        this.nome = nome;
    }

    public String getDescricao() {
        return this.descricao;
    }

    public void setDescricao(String descricao) {
        this.descricao = descricao;
    }

    public boolean isAtivo() {
        return this.ativo;
    }

    public void setAtivo(boolean ativo) {
        this.ativo = ativo;
    }

    public double getPreco() {
        return this.preco;
    }

    public void setPreco(double preco) {
        this.preco = preco;
    }

    @JsonIgnore
    public List<ProdutoVenda> getProdutosVenda() {
        return this.produtosVenda;
    }

    public void setProdutosVenda(List<ProdutoVenda> produtosVenda) {
        this.produtosVenda = produtosVenda;
    }
}
