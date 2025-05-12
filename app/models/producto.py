from app import db

class Producto(db.Model):

    __tablename__="producto"
    id = db.Column(db.Integer, primary_key=True)
    Producto = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Strig(100), nullable=False)
    precio = db.Column(db.Float, nullable=False)
    cantidad = db.Column(db.Integer, nullable=False)
    imagen = db.Column(db.String(255), nullable=True) 
    categoria = db.relationship('Categoria', backref='productos')
