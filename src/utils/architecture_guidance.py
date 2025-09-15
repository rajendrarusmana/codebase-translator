"""
Architecture Guidance Module - Framework mappings and architectural patterns.

This module provides comprehensive mappings between frameworks across different languages,
helping translate architectural patterns and dependencies during codebase migration.
"""
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum


class FrameworkCategory(Enum):
    """Categories of frameworks."""
    WORKER = "worker"
    WEB_API = "web_api"
    WEB_FULL = "web_full"
    CLI = "cli"
    TESTING = "testing"
    ORM = "orm"
    MESSAGING = "messaging"
    MICROSERVICE = "microservice"


@dataclass
class FrameworkInfo:
    """Information about a framework."""
    name: str
    category: FrameworkCategory
    language: str
    description: str
    features: List[str]
    dependencies: List[str]
    package_manager: str
    entry_pattern: str  # Pattern for main entry file


@dataclass
class FrameworkMapping:
    """Mapping between source and target frameworks."""
    source: FrameworkInfo
    target: FrameworkInfo
    compatibility_score: float  # 0.0 to 1.0
    migration_notes: List[str]
    pattern_mappings: Dict[str, str]  # Source pattern -> Target pattern


class ArchitectureGuidance:
    """Provides architectural guidance for framework translation."""

    def __init__(self):
        self.frameworks = self._initialize_frameworks()
        self.mappings = self._initialize_mappings()

    def _initialize_frameworks(self) -> Dict[str, FrameworkInfo]:
        """Initialize framework database."""
        return {
            # Ruby Frameworks
            'ruby/sidekiq': FrameworkInfo(
                name='sidekiq',
                category=FrameworkCategory.WORKER,
                language='ruby',
                description='Background job processing framework',
                features=['redis_queue', 'retry_logic', 'scheduled_jobs', 'web_ui'],
                dependencies=['redis', 'connection_pool'],
                package_manager='bundler',
                entry_pattern='workers/*.rb'
            ),
            'ruby/rails': FrameworkInfo(
                name='rails',
                category=FrameworkCategory.WEB_FULL,
                language='ruby',
                description='Full-stack web framework',
                features=['mvc', 'orm', 'routing', 'middleware', 'assets'],
                dependencies=['active_record', 'action_controller', 'action_view'],
                package_manager='bundler',
                entry_pattern='config/application.rb'
            ),

            # Go Frameworks
            'go/asynq': FrameworkInfo(
                name='asynq',
                category=FrameworkCategory.WORKER,
                language='go',
                description='Distributed task queue with Redis',
                features=['redis_queue', 'retry_logic', 'scheduled_jobs', 'web_ui', 'middleware'],
                dependencies=['github.com/hibiken/asynq', 'github.com/go-redis/redis'],
                package_manager='go_modules',
                entry_pattern='main.go'
            ),
            'go/machinery': FrameworkInfo(
                name='machinery',
                category=FrameworkCategory.WORKER,
                language='go',
                description='Distributed task queue supporting multiple brokers',
                features=['multi_broker', 'workflows', 'chains', 'groups', 'callbacks'],
                dependencies=['github.com/RichardKnox/machinery'],
                package_manager='go_modules',
                entry_pattern='main.go'
            ),
            'go/gin': FrameworkInfo(
                name='gin',
                category=FrameworkCategory.WEB_API,
                language='go',
                description='HTTP web framework',
                features=['routing', 'middleware', 'json_binding', 'validation'],
                dependencies=['github.com/gin-gonic/gin'],
                package_manager='go_modules',
                entry_pattern='main.go'
            ),
            'go/echo': FrameworkInfo(
                name='echo',
                category=FrameworkCategory.WEB_API,
                language='go',
                description='High performance web framework',
                features=['routing', 'middleware', 'websocket', 'http2'],
                dependencies=['github.com/labstack/echo/v4'],
                package_manager='go_modules',
                entry_pattern='main.go'
            ),
            'go/fiber': FrameworkInfo(
                name='fiber',
                category=FrameworkCategory.WEB_API,
                language='go',
                description='Express-inspired web framework',
                features=['routing', 'middleware', 'websocket', 'fast'],
                dependencies=['github.com/gofiber/fiber/v2'],
                package_manager='go_modules',
                entry_pattern='main.go'
            ),

            # Python Frameworks
            'python/celery': FrameworkInfo(
                name='celery',
                category=FrameworkCategory.WORKER,
                language='python',
                description='Distributed task queue',
                features=['multi_broker', 'result_backend', 'scheduling', 'workflows'],
                dependencies=['celery', 'redis', 'kombu'],
                package_manager='pip',
                entry_pattern='celery_app.py'
            ),
            'python/django': FrameworkInfo(
                name='django',
                category=FrameworkCategory.WEB_FULL,
                language='python',
                description='High-level web framework',
                features=['orm', 'admin', 'auth', 'sessions', 'migrations'],
                dependencies=['django'],
                package_manager='pip',
                entry_pattern='manage.py'
            ),
            'python/fastapi': FrameworkInfo(
                name='fastapi',
                category=FrameworkCategory.WEB_API,
                language='python',
                description='Modern API framework',
                features=['async', 'openapi', 'validation', 'dependency_injection'],
                dependencies=['fastapi', 'uvicorn', 'pydantic'],
                package_manager='pip',
                entry_pattern='main.py'
            ),
            'python/flask': FrameworkInfo(
                name='flask',
                category=FrameworkCategory.WEB_API,
                language='python',
                description='Micro web framework',
                features=['routing', 'templates', 'sessions', 'blueprints'],
                dependencies=['flask'],
                package_manager='pip',
                entry_pattern='app.py'
            ),

            # JavaScript/Node Frameworks
            'javascript/bull': FrameworkInfo(
                name='bull',
                category=FrameworkCategory.WORKER,
                language='javascript',
                description='Redis-based queue for Node',
                features=['redis_queue', 'priority', 'delayed_jobs', 'rate_limiting'],
                dependencies=['bull', 'ioredis'],
                package_manager='npm',
                entry_pattern='worker.js'
            ),
            'javascript/express': FrameworkInfo(
                name='express',
                category=FrameworkCategory.WEB_API,
                language='javascript',
                description='Minimal web framework',
                features=['routing', 'middleware', 'template_engines', 'static_files'],
                dependencies=['express'],
                package_manager='npm',
                entry_pattern='app.js'
            ),
            'javascript/nestjs': FrameworkInfo(
                name='nestjs',
                category=FrameworkCategory.WEB_API,
                language='javascript',
                description='Progressive Node.js framework',
                features=['dependency_injection', 'decorators', 'modules', 'microservices'],
                dependencies=['@nestjs/core', '@nestjs/common'],
                package_manager='npm',
                entry_pattern='main.ts'
            ),

            # Java Frameworks
            'java/spring': FrameworkInfo(
                name='spring',
                category=FrameworkCategory.WEB_FULL,
                language='java',
                description='Comprehensive application framework',
                features=['dependency_injection', 'aop', 'mvc', 'data_access', 'security'],
                dependencies=['spring-boot-starter-web'],
                package_manager='maven',
                entry_pattern='Application.java'
            ),
        }

    def _initialize_mappings(self) -> List[FrameworkMapping]:
        """Initialize framework mappings."""
        return [
            # Worker Framework Mappings
            FrameworkMapping(
                source=self.frameworks['ruby/sidekiq'],
                target=self.frameworks['go/asynq'],
                compatibility_score=0.95,
                migration_notes=[
                    'Both use Redis as message broker',
                    'Similar job retry and scheduling features',
                    'Web UI available in both',
                    'Middleware support in both'
                ],
                pattern_mappings={
                    'include Sidekiq::Worker': 'implements asynq.Handler',
                    'perform()': 'ProcessTask()',
                    'perform_async': 'client.Enqueue()',
                    'perform_in': 'client.EnqueueIn()',
                    'sidekiq_options': 'asynq.Config',
                }
            ),
            FrameworkMapping(
                source=self.frameworks['ruby/sidekiq'],
                target=self.frameworks['go/machinery'],
                compatibility_score=0.85,
                migration_notes=[
                    'Machinery supports multiple brokers beyond Redis',
                    'More complex workflow capabilities',
                    'Different API patterns'
                ],
                pattern_mappings={
                    'include Sidekiq::Worker': 'machinery.RegisterTask',
                    'perform()': 'Run()',
                    'perform_async': 'SendTask()',
                }
            ),
            FrameworkMapping(
                source=self.frameworks['python/celery'],
                target=self.frameworks['go/machinery'],
                compatibility_score=0.90,
                migration_notes=[
                    'Both support multiple brokers',
                    'Similar workflow capabilities',
                    'Task chaining and grouping supported'
                ],
                pattern_mappings={
                    '@app.task': 'RegisterTask()',
                    'apply_async()': 'SendTask()',
                    'chain()': 'NewChain()',
                    'group()': 'NewGroup()',
                }
            ),

            # Web Framework Mappings
            FrameworkMapping(
                source=self.frameworks['ruby/rails'],
                target=self.frameworks['go/gin'],
                compatibility_score=0.70,
                migration_notes=[
                    'Gin is API-focused, not full-stack like Rails',
                    'No built-in ORM, use GORM separately',
                    'Manual routing instead of convention-based',
                    'Middleware pattern similar to Rails'
                ],
                pattern_mappings={
                    'class Controller < ApplicationController': 'gin.HandlerFunc',
                    'before_action': 'gin.Middleware',
                    'render json:': 'c.JSON()',
                    'params[]': 'c.Param() / c.Query()',
                    'redirect_to': 'c.Redirect()',
                }
            ),
            FrameworkMapping(
                source=self.frameworks['python/django'],
                target=self.frameworks['go/fiber'],
                compatibility_score=0.75,
                migration_notes=[
                    'Fiber has Express-like API',
                    'No built-in admin interface',
                    'Use GORM for ORM functionality',
                    'Manual authentication setup required'
                ],
                pattern_mappings={
                    'class View': 'fiber.Handler',
                    'urlpatterns': 'app.Route()',
                    'HttpResponse': 'c.Send()',
                    'render()': 'c.Render()',
                }
            ),
            FrameworkMapping(
                source=self.frameworks['javascript/express'],
                target=self.frameworks['go/gin'],
                compatibility_score=0.85,
                migration_notes=[
                    'Similar middleware pattern',
                    'Similar routing API',
                    'Both support JSON APIs well'
                ],
                pattern_mappings={
                    'app.get()': 'router.GET()',
                    'app.post()': 'router.POST()',
                    'app.use()': 'router.Use()',
                    'req.params': 'c.Param()',
                    'req.query': 'c.Query()',
                    'res.json()': 'c.JSON()',
                    'res.send()': 'c.String()',
                }
            ),
        ]

    def get_framework_info(self, framework_key: str) -> Optional[FrameworkInfo]:
        """Get framework information by key."""
        return self.frameworks.get(framework_key)

    def find_best_target_framework(
        self,
        source_framework: str,
        source_language: str,
        target_language: str
    ) -> Optional[Tuple[FrameworkInfo, FrameworkMapping]]:
        """Find the best target framework for migration."""
        source_key = f"{source_language}/{source_framework}"
        source_info = self.frameworks.get(source_key)

        if not source_info:
            return None

        best_mapping = None
        best_score = 0.0

        for mapping in self.mappings:
            if mapping.source.name == source_framework and \
               mapping.target.language == target_language:
                if mapping.compatibility_score > best_score:
                    best_score = mapping.compatibility_score
                    best_mapping = mapping

        if best_mapping:
            return (best_mapping.target, best_mapping)

        # Fallback: find any framework in target language with same category
        for framework_key, framework_info in self.frameworks.items():
            if framework_info.language == target_language and \
               framework_info.category == source_info.category:
                # Create a basic mapping
                basic_mapping = FrameworkMapping(
                    source=source_info,
                    target=framework_info,
                    compatibility_score=0.5,
                    migration_notes=['Automatic fallback mapping'],
                    pattern_mappings={}
                )
                return (framework_info, basic_mapping)

        return None

    def get_dependency_mapping(
        self,
        source_dep: str,
        source_language: str,
        target_language: str
    ) -> Optional[str]:
        """Map a dependency from source to target language."""
        dependency_map = {
            ('ruby', 'go'): {
                'redis': 'github.com/go-redis/redis/v8',
                'pg': 'github.com/lib/pq',
                'mysql2': 'github.com/go-sql-driver/mysql',
                'mongoid': 'go.mongodb.org/mongo-driver',
                'httparty': 'net/http',
                'faraday': 'net/http',
            },
            ('python', 'go'): {
                'redis': 'github.com/go-redis/redis/v8',
                'psycopg2': 'github.com/lib/pq',
                'pymongo': 'go.mongodb.org/mongo-driver',
                'requests': 'net/http',
                'aiohttp': 'net/http',
                'sqlalchemy': 'github.com/jinzhu/gorm',
            },
            ('javascript', 'go'): {
                'redis': 'github.com/go-redis/redis/v8',
                'pg': 'github.com/lib/pq',
                'mongodb': 'go.mongodb.org/mongo-driver',
                'axios': 'net/http',
                'express': 'github.com/gin-gonic/gin',
                'sequelize': 'github.com/jinzhu/gorm',
            },
        }

        key = (source_language.lower(), target_language.lower())
        if key in dependency_map:
            return dependency_map[key].get(source_dep.lower())

        return None

    def get_project_structure_template(
        self,
        framework: FrameworkInfo,
        project_type: str
    ) -> Dict[str, Any]:
        """Get recommended project structure for a framework."""
        structures = {
            'go/asynq': {
                'directories': [
                    'cmd/worker',
                    'internal/workers',
                    'internal/config',
                    'internal/models',
                    'pkg/redis',
                    'scripts',
                    'deployments',
                ],
                'files': {
                    'go.mod': 'module_definition',
                    'go.sum': 'dependency_lock',
                    'Makefile': 'build_commands',
                    'Dockerfile': 'container_definition',
                    '.env.example': 'environment_template',
                    'README.md': 'documentation',
                }
            },
            'go/gin': {
                'directories': [
                    'cmd/api',
                    'internal/handlers',
                    'internal/middleware',
                    'internal/models',
                    'internal/services',
                    'pkg/database',
                    'configs',
                    'docs',
                ],
                'files': {
                    'go.mod': 'module_definition',
                    'go.sum': 'dependency_lock',
                    'Makefile': 'build_commands',
                    'Dockerfile': 'container_definition',
                    'docker-compose.yml': 'local_services',
                    '.env.example': 'environment_template',
                }
            },
            'python/celery': {
                'directories': [
                    'app',
                    'app/workers',
                    'app/models',
                    'config',
                    'tests',
                    'scripts',
                ],
                'files': {
                    'requirements.txt': 'dependencies',
                    'requirements-dev.txt': 'dev_dependencies',
                    'celery_app.py': 'celery_initialization',
                    'Dockerfile': 'container_definition',
                    'docker-compose.yml': 'local_services',
                    '.env.example': 'environment_template',
                    'Makefile': 'commands',
                }
            },
        }

        framework_key = f"{framework.language}/{framework.name}"
        return structures.get(framework_key, {
            'directories': ['src', 'tests', 'docs'],
            'files': {'README.md': 'documentation'}
        })


# Singleton instance
architecture_guidance = ArchitectureGuidance()
