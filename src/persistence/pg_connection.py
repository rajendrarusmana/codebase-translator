"""
PostgreSQL connection management with async pool support.
"""
import asyncio
import asyncpg
import logging
from typing import Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class PostgreSQLConnection:
    """Manages PostgreSQL connection pool for the documentation system."""
    
    def __init__(self, database_url: str, min_connections: int = 5, max_connections: int = 20):
        self.database_url = database_url
        self.min_connections = min_connections
        self.max_connections = max_connections
        self.pool: Optional[asyncpg.Pool] = None
        self._initialized = False
    
    async def initialize(self, postgres_config: Dict[str, Any] = None):
        """Initialize the connection pool and create schema if needed."""
        if self._initialized:
            return
            
        try:
            logger.info("Initializing PostgreSQL connection pool...")
            self.pool = await asyncpg.create_pool(
                self.database_url,
                min_size=self.min_connections,
                max_size=self.max_connections
            )
            
            logger.info("PostgreSQL pool initialized with {}-{} connections".format(
                self.min_connections, self.max_connections
            ))
            
            # Initialize database schema if enabled
            if postgres_config and postgres_config.get('initialize_schema', True):
                await self._initialize_schema(postgres_config)
            
            self._initialized = True
            
        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL connection pool: {e}")
            raise RuntimeError(f"PostgreSQL connection pool initialization failed: {e}")
    
    async def _initialize_schema(self, postgres_config: Dict[str, Any]):
        """Initialize database schema from configuration."""
        try:
            logger.info("Initializing database schema...")
            
            # Handle case where postgres_config might be a string (schema file path)
            if isinstance(postgres_config, str):
                schema_file_path = postgres_config
            else:
                # Get schema file path from config or use default
                schema_file_path = postgres_config.get('schema_file', 'src/persistence/schema_simple.sql') if postgres_config else 'src/persistence/schema_simple.sql'
            
            schema_path = Path(schema_file_path)
            
            # If relative path, resolve from project root
            if not schema_path.is_absolute():
                schema_path = Path(__file__).parent.parent.parent / schema_path
            
            if not schema_path.exists():
                logger.warning(f"Schema file not found: {schema_path}")
                # Try default schema
                default_schema = Path(__file__).parent / "schema_simple.sql"
                if default_schema.exists():
                    schema_path = default_schema
                else:
                    # Try legacy schema
                    legacy_schema = Path(__file__).parent / "schema.sql"
                    if legacy_schema.exists():
                        schema_path = legacy_schema
                    else:
                        raise FileNotFoundError(f"No schema file found at {schema_file_path} or default locations")
            
            # Read and execute schema
            with open(schema_path, 'r', encoding='utf-8') as f:
                schema_sql = f.read()
            
            # Split schema into individual statements and execute each one
            # Split by semicolon and filter out empty statements and comments
            statements = [stmt.strip() for stmt in schema_sql.split(';') if stmt.strip()]
            
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    for statement in statements:
                        # Skip comments and empty statements
                        if statement and not statement.startswith('--') and not statement.startswith('/*'):
                            try:
                                await conn.execute(statement)
                            except Exception as e:
                                logger.warning(f"Failed to execute statement: {statement[:100]}... Error: {e}")
                                # Continue with other statements
            
            logger.info(f"Database schema initialized successfully from: {schema_path}")
            
        except Exception as e:
            logger.error(f"Failed to initialize database schema: {e}")
            raise
    
    async def initialize_schema(self, postgres_config: Dict[str, Any] = None):
        """Public method to initialize database schema."""
        await self._initialize_schema(postgres_config)
    
    async def close(self):
        """Close the connection pool."""
        if self.pool:
            await self.pool.close()
            logger.info("PostgreSQL connection pool closed")
            self._initialized = False
    
    def get_pool(self) -> asyncpg.Pool:
        """Get the connection pool for use by repositories."""
        if not self._initialized or not self.pool:
            raise RuntimeError("Connection pool not initialized. Call initialize() first.")
        return self.pool
    
    async def health_check(self) -> Dict[str, Any]:
        """Check database health and connection status."""
        if not self.pool:
            return {"status": "disconnected", "error": "Pool not initialized"}
        
        try:
            async with self.pool.acquire() as conn:
                # Test basic query
                result = await conn.fetchval("SELECT 1")
                
                # Get pool stats
                pool_stats = {
                    "size": self.pool.get_size(),
                    "min_size": self.pool.get_min_size(),
                    "max_size": self.pool.get_max_size(),
                    "idle_size": self.pool.get_idle_size()
                }
                
                # Get database info
                db_info = await conn.fetchrow("""
                    SELECT 
                        version() as version,
                        current_database() as database,
                        current_user as user
                """)
                
                return {
                    "status": "healthy",
                    "test_query": result,
                    "pool_stats": pool_stats,
                    "database_info": dict(db_info)
                }
                
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def execute_query(self, query: str, *args) -> Any:
        """Execute a single query (for maintenance tasks)."""
        if not self.pool:
            raise RuntimeError("Connection pool not initialized")
        
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, *args)
    
    async def execute_many(self, queries: list) -> None:
        """Execute multiple queries in a transaction."""
        if not self.pool:
            raise RuntimeError("Connection pool not initialized")
        
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                for query, args in queries:
                    await conn.execute(query, *args if args else ())


class DatabaseManager:
    """High-level database manager for the codebase translator."""
    
    _instance: Optional['DatabaseManager'] = None
    
    def __init__(self):
        self.connection: Optional[PostgreSQLConnection] = None
        self._config: Dict[str, Any] = {}
    
    @classmethod
    def get_instance(cls) -> 'DatabaseManager':
        """Get singleton instance of DatabaseManager."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    async def initialize(self, database_config: Dict[str, Any]):
        """Initialize database connection with configuration."""
        self._config = database_config
        
        database_url = database_config.get('url')
        if not database_url:
            raise ValueError("Database URL is required")
        
        min_connections = database_config.get('min_connections', 5)
        max_connections = database_config.get('max_connections', 20)
        
        self.connection = PostgreSQLConnection(
            database_url=database_url,
            min_connections=min_connections,
            max_connections=max_connections
        )
        
        await self.connection.initialize()
        
        # Initialize schema if configured
        if database_config.get('initialize_schema', True):
            schema_file = database_config.get('schema_file')
            await self.connection.initialize_schema(schema_file)
    
    async def close(self):
        """Close database connection."""
        if self.connection:
            await self.connection.close()
            self.connection = None
    
    def get_connection(self) -> PostgreSQLConnection:
        """Get database connection for repositories."""
        if not self.connection:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        return self.connection
    
    async def health_check(self) -> Dict[str, Any]:
        """Get database health status."""
        if not self.connection:
            return {"status": "not_initialized"}
        
        return await self.connection.health_check()


# Global database manager instance
db_manager = DatabaseManager.get_instance()