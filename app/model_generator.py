from app.db_connection import tables
from sqlalchemy.orm import declarative_base
import warnings
from sqlalchemy.exc import SAWarning

warnings.simplefilter('ignore', category=SAWarning)


Base = declarative_base()

class Model_Generator:
    def __init__(self,tables):
        self.tables = tables
        self.generated_models={}
        self.generate_models()

    def generate_models(self):
        for table_name,base_model in self.tables.items():
            class_name = f"Generated {table_name.capitalize()}"

            model_rels = {
                "__tablename__":table_name,
                "__table__":base_model.__table__,
                "_original_model":base_model,
                "__module__":f"generated_models.{table_name}"
            }

            for attr in dir(base_model):
                if hasattr(getattr(base_model, attr),'property'):
                    model_rels[attr] = getattr(base_model, attr)
            
            model_rels.update({
                'create':classmethod(self.create),
                'read':classmethod(self.read),
                'update':classmethod(self.update),
                'delete':classmethod(self.delete),
                'query_all':classmethod(self.query_all)
                })
            
            model_class = type(
                class_name,
                (tables().base,),
                model_rels
            )
            self.generated_models[table_name] = model_class
        
    @staticmethod
    def create(cls, session, **kwargs):
        instance = cls(**kwargs)
        session.add(instance)
        session.commit()
        return instance
    
    @staticmethod
    def read(cls, session, **kwargs):
        return session.query(cls).filter_by(**kwargs).first()
    
    def update(self, session, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
        session.commit()
        return self
    
    def delete(self, session):
        session.delete(self)
        session.commit()
    
    @staticmethod
    def query(cls, session, **kwargs):
        return session.query(cls).filter_by(**kwargs)

    @staticmethod
    def query_all(cls, session):
        return session.query(cls).all()
    
    @classmethod
    def get_models(cls):
        tables_instance = tables()
        session = tables_instance.create_session()
        model_generator = cls(tables_instance.models)
        return model_generator.generated_models, session