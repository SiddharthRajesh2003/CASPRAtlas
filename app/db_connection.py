from flask import Flask
from sqlalchemy import create_engine, MetaData, inspect
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from sqlalchemy.exc import SQLAlchemyError
from contextlib import contextmanager
from dotenv import load_dotenv
import os
import logging
import pymysql

pymysql.install_as_MySQLdb()
load_dotenv()
base = declarative_base()

class Connection:
    def __init__(self):
        url = os.getenv('db_url')
        self.app=Flask(__name__)
        self.app.logger.setLevel(logging.INFO)
        if not url:
            self.app.logger.info("Database URL Not available")
        
        self.base = base
        self.app.config['SQLALCHEMY_DATABASE_URI']= f'mysql+pymysql://{url}'
        self.app.secret_key = os.getenv('secret_key')
        self.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

        self.engine = create_engine(self.app.config['SQLALCHEMY_DATABASE_URI'])
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    @contextmanager
    def db_session(self):
        session = self.SessionLocal()
   
        try:
            yield session
            session.commit()
        except:
            session.rollback()
            raise
        finally:
            session.close()
    

    def test_connect(self):
        try:
            with self.engine.connect() as connection:
                self.app.logger.info("Successfully connected to the database.")
                return "Connected!"
        except SQLAlchemyError as e:
            self.app.logger.error(f"Database connection failed: {e}")
            raise

class tables(Connection):
    def __init__(self):
        super().__init__()
        self.metadata = MetaData()
        self.base=base
        self.models = {}
        self.load_schema()
        self._models()
        base.metadata.reflect(bind=self.engine)

    def load_schema(self):
        self.metadata.reflect(bind = self.engine)
        for table_name, table in self.metadata.tables.items():
            model_class = type(
                table_name, 
                (self.base,), 
                {
                    '__tablename__': table_name,
                    '__table__': table,
                }
            )
            
            # Store the model
            self.models[table_name] = model_class

    def _models(self):
        inspector = inspect(self.engine)

        for table_name, model in self.models.items():
            fkeys = inspector.get_foreign_keys(table_name)

            for fk in fkeys:
                if fk['constrained_columns'] and fk['referred_table']:
                    column = fk['constrained_columns'][0]
                    referred_table = fk['referred_table']
                    ref_col = fk['referred_columns'][0]

                    rel_name = f'{ referred_table}_relationship'

                    setattr(model,
                            rel_name,
                            relationship(
                                self.models[referred_table],
                                foreign_keys=[model.__table__.c[column]]
                            ))
        return self.models
    
    def create_session(self):
        session = sessionmaker(bind=self.engine)
        self.app.logger.info('Created the session')
        return session()
    
    def check_tables(self):
        print("Tables in the database:")
        for table_name in self.metadata.tables.keys():
            self.app.logger.info(table_name)
            print(table_name)
    
    def check_foreign_keys(self):
        inspector = inspect(self.engine)
        print("Foreign Keys in the Database:")

        for table_name in self.metadata.tables.keys():
            fkeys = inspector.get_foreign_keys(table_name)
            
            if fkeys:
                print(f"\nTable: {table_name}")
                for fk in fkeys:
                    self.app.logger.info(f"  Column: {fk['constrained_columns']} -> {fk['referred_table']}({fk['referred_columns']})")
                    print(f"  Column: {fk['constrained_columns']} -> {fk['referred_table']}({fk['referred_columns']})")
            else:
                print(f"\nTable: {table_name} has no foreign keys.")
    
    def import_rows(self):
        """
        Imports all rows from each table in the database into their corresponding models.
        Returns a dictionary where keys are table names and values are lists of model instances.
        """
        data = {}
        with self.db_session() as session:
            for table_name, model in self.models.items():
                # Query all rows from the current table/model
                data[table_name] = session.query(model).all()
        return data