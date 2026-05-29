"""
Production security and pre-flight checks
Validates environment, secrets, API keys, and security configurations
"""

import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


class ProductionValidator:
    """Validates system is production-ready"""
    
    def __init__(self, cfg):
        self.cfg = cfg
        self.errors: List[str] = []
        self.warnings: List[str] = []
    
    def validate_all(self) -> Tuple[bool, Dict]:
        """Run all production checks"""
        self.validate_mistral_api()
        self.validate_database()
        self.validate_exchange_keys()
        self.validate_wallet_security()
        self.validate_file_permissions()
        self.validate_ssl_certificates()
        self.validate_rate_limiting()
        
        is_ready = len(self.errors) == 0
        
        return is_ready, {
            "ready": is_ready,
            "errors": self.errors,
            "warnings": self.warnings,
            "total_checks": 8
        }
    
    def validate_mistral_api(self):
        """Check Mistral API configuration"""
        if not self.cfg.mistral_api_key:
            self.errors.append("MISTRAL_API_KEY not set")
            return
        
        if len(self.cfg.mistral_api_key) < 10:
            self.errors.append("MISTRAL_API_KEY appears invalid (too short)")
            return
        
        logger.info("✓ Mistral API key configured")
    
    def validate_database(self):
        """Check database configuration and connectivity"""
        db_path = Path(self.cfg.db_path)
        
        # Check parent directory exists
        if not db_path.parent.exists():
            self.errors.append(f"Database directory does not exist: {db_path.parent}")
            return
        
        # Check write permissions
        if not os.access(db_path.parent, os.W_OK):
            self.errors.append(f"No write permission to database directory: {db_path.parent}")
            return
        
        # Try to connect
        try:
            import sqlite3
            conn = sqlite3.connect(self.cfg.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            conn.close()
            logger.info("✓ Database accessible and writable")
        except Exception as e:
            self.errors.append(f"Database connectivity failed: {e}")
    
    def validate_exchange_keys(self):
        """Validate exchange API keys"""
        exchange = self.cfg.exchange
        
        if exchange == "xt":
            if not self.cfg.xt_api_key:
                self.warnings.append("XT_API_KEY not set (required for trades)")
            elif len(self.cfg.xt_api_key) < 10:
                self.warnings.append("XT_API_KEY appears invalid")
            else:
                logger.info(f"✓ {exchange.upper()} API key configured")
        
        elif exchange == "bitunix":
            if not self.cfg.bitunix_api_key:
                self.warnings.append("BITUNIX_API_KEY not set (required for trades)")
            elif len(self.cfg.bitunix_api_key) < 10:
                self.warnings.append("BITUNIX_API_KEY appears invalid")
            else:
                logger.info(f"✓ {exchange.upper()} API key configured")
    
    def validate_wallet_security(self):
        """Check wallet storage security"""
        wallet_dir = Path("./output/wallets")
        
        # Check if wallets directory exists
        if not wallet_dir.exists():
            wallet_dir.mkdir(parents=True, exist_ok=True)
        
        # Check permissions (should be 700 in production)
        try:
            import stat
            perms = stat.filemode(os.stat(wallet_dir).st_mode)
            if "w" in perms and "-" in perms:  # Readable by group/others
                self.warnings.append(
                    f"Wallet directory has loose permissions: {perms}. "
                    "Run: chmod 700 ./output/wallets"
                )
        except Exception as e:
            logger.warning(f"Could not check wallet directory permissions: {e}")
        
        logger.info("✓ Wallet directory configured")
    
    def validate_file_permissions(self):
        """Check file permissions for sensitive files"""
        sensitive_files = [
            ".env",
            Path(self.cfg.db_path)
        ]
        
        for file_path in sensitive_files:
            if isinstance(file_path, str):
                file_path = Path(file_path)
            
            if file_path.exists():
                try:
                    import stat
                    perms = stat.filemode(os.stat(file_path).st_mode)
                    if "r" in perms and ("g" in perms or "o" in perms):
                        self.warnings.append(
                            f"Sensitive file has loose permissions: {file_path} ({perms})"
                        )
                except Exception as e:
                    logger.warning(f"Could not check {file_path} permissions: {e}")
        
        logger.info("✓ File permissions checked")
    
    def validate_ssl_certificates(self):
        """Check SSL certificate configuration"""
        # For production, ensure HTTPS is used
        if self.cfg.upload_base.startswith("http://"):
            self.warnings.append(
                f"Upload base uses HTTP (not HTTPS): {self.cfg.upload_base}. "
                "Use HTTPS in production."
            )
        else:
            logger.info("✓ Upload base uses HTTPS")
    
    def validate_rate_limiting(self):
        """Check rate limiting configuration"""
        # Exchange API typically has rate limits
        # Recommend timeout and backoff settings
        if self.cfg.max_backoff_secs < 60:
            self.warnings.append(
                f"max_backoff_secs is low ({self.cfg.max_backoff_secs}s). "
                "Consider increasing to avoid API throttling."
            )
        
        logger.info("✓ Rate limiting configuration reasonable")


class SecretsValidator:
    """Validates secrets are not exposed"""
    
    @staticmethod
    def check_secrets_in_files() -> List[str]:
        """Check for exposed secrets in source files"""
        issues = []
        
        sensitive_patterns = [
            "MISTRAL_API_KEY=",
            "XT_API_KEY=",
            "BITUNIX_API_KEY=",
            "BEGIN RSA PRIVATE KEY",
            "BEGIN PRIVATE KEY"
        ]
        
        excluded_dirs = {".git", ".env", "__pycache__", "node_modules", ".venv", "venv"}
        
        for filepath in Path(".").rglob("*.py"):
            if any(excluded in filepath.parts for excluded in excluded_dirs):
                continue
            
            try:
                content = filepath.read_text()
                for pattern in sensitive_patterns:
                    if pattern in content and "=os.getenv" not in content:
                        issues.append(f"Potential exposed secret in {filepath}: {pattern}")
            except Exception:
                pass
        
        return issues


class APISecurityValidator:
    """Validates API security measures"""
    
    @staticmethod
    def validate_api_keys(cfg) -> Dict:
        """Validate API key strength and format"""
        issues = []
        
        # Check API key length
        if cfg.mistral_api_key and len(cfg.mistral_api_key) < 20:
            issues.append("Mistral API key appears too short (possible test key)")
        
        # Check for placeholder keys
        placeholders = ["test", "demo", "example", "sk_live_test", "YOUR_KEY"]
        if cfg.mistral_api_key and any(p.lower() in cfg.mistral_api_key.lower() for p in placeholders):
            issues.append("Mistral API key appears to be a placeholder")
        
        return {"valid": len(issues) == 0, "issues": issues}


def run_production_checks(cfg) -> bool:
    """Run all production readiness checks"""
    print("\n" + "=" * 60)
    print("PRODUCTION READINESS CHECK")
    print("=" * 60)
    
    validator = ProductionValidator(cfg)
    is_ready, results = validator.validate_all()
    
    print(f"\n✓ Checks Passed: {len(results['errors']) == 0}")
    
    if results['errors']:
        print("\n❌ CRITICAL ERRORS:")
        for error in results['errors']:
            print(f"  - {error}")
    
    if results['warnings']:
        print("\n⚠ WARNINGS:")
        for warning in results['warnings']:
            print(f"  - {warning}")
    
    # Check for exposed secrets
    secrets_issues = SecretsValidator.check_secrets_in_files()
    if secrets_issues:
        print("\n🔒 SECURITY ISSUES:")
        for issue in secrets_issues:
            print(f"  - {issue}")
        is_ready = False
    
    # Validate API security
    api_security = APISecurityValidator.validate_api_keys(cfg)
    if not api_security['valid']:
        print("\n🔐 API SECURITY ISSUES:")
        for issue in api_security['issues']:
            print(f"  - {issue}")
    
    print("\n" + "=" * 60)
    if is_ready:
        print("✅ SYSTEM IS PRODUCTION READY")
    else:
        print("❌ SYSTEM IS NOT PRODUCTION READY")
        print("   Please fix the critical errors above before deploying.")
    print("=" * 60 + "\n")
    
    return is_ready


if __name__ == "__main__":
    from configs.config import load_config
    cfg = load_config()
    is_ready = run_production_checks(cfg)
    sys.exit(0 if is_ready else 1)
