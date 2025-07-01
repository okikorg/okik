import chalk from 'chalk';
import gradient from 'gradient-string';
import { createSpinner } from 'nanospinner';
import winston from 'winston';
import { LogLevel } from '../types/index.js';

// Define color themes
export const theme = {
  primary: chalk.cyan,
  secondary: chalk.blue,
  success: chalk.green,
  warning: chalk.yellow,
  error: chalk.red,
  info: chalk.blue,
  muted: chalk.gray,
  accent: gradient('cyan', 'magenta')
};

// Configure Winston logger
const logger = winston.createLogger({
  level: 'info',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.errors({ stack: true }),
    winston.format.json()
  ),
  defaultMeta: { service: 'okik' },
  transports: [
    new winston.transports.File({ 
      filename: '.okik.log',
      maxsize: 10 * 1024 * 1024, // 10MB
      maxFiles: 10
    })
  ]
});

// Enhanced console formatting
const consoleFormat = winston.format.printf(({ level, message, timestamp }) => {
  return `${chalk.gray(timestamp)} ${message}`;
});

if (process.env.NODE_ENV !== 'production') {
  logger.add(new winston.transports.Console({
    format: consoleFormat
  }));
}

// Logging functions with enhanced TUI
export function logStart(message: string): void {
  const formatted = `${theme.primary('▶')} ${theme.primary('Starting:')} ${message}`;
  console.log(formatted);
  logger.info(`Starting: ${message}`);
}

export function logRunning(message: string): void {
  const formatted = `${theme.info('⚡')} ${theme.info('Running:')} ${message}`;
  console.log(formatted);
  logger.info(`Running: ${message}`);
}

export function logSuccess(message: string): void {
  const formatted = `${theme.success('✅')} ${theme.success('Success:')} ${message}`;
  console.log(formatted);
  logger.info(`Success: ${message}`);
}

export function logError(message: string): void {
  const formatted = `${theme.error('❌')} ${theme.error('Error:')} ${message}`;
  console.error(formatted);
  logger.error(`Error: ${message}`);
}

export function logWarning(message: string): void {
  const formatted = `${theme.warning('⚠️')} ${theme.warning('Warning:')} ${message}`;
  console.warn(formatted);
  logger.warn(`Warning: ${message}`);
}

export function logInfo(message: string): void {
  const formatted = `${theme.info('ℹ️')} ${theme.info('Info:')} ${message}`;
  console.log(formatted);
  logger.info(`Info: ${message}`);
}

export function logDebug(message: string): void {
  const formatted = `${theme.muted('🔍')} ${theme.muted('Debug:')} ${message}`;
  console.log(formatted);
  logger.debug(`Debug: ${message}`);
}

// Enhanced progress indicators
export function createProgressSpinner(text: string) {
  return createSpinner(text).start();
}

export function logStep(step: number, total: number, message: string): void {
  const progress = `${theme.muted(`[${step}/${total}]`)}`;
  const formatted = `${progress} ${theme.primary('▶')} ${message}`;
  console.log(formatted);
  logger.info(`Step ${step}/${total}: ${message}`);
}

// ASCII Art utilities
export function printBanner(): void {
  const banner = theme.accent(`
  ██████  ██   ██ ██ ██   ██
  ██    ██ ██  ██  ██ ██  ██
  ██    ██ █████   ██ █████  
  ██    ██ ██  ██  ██ ██  ██ 
  ██████  ██   ██ ██ ██   ██ 
  
  `);
  
  console.log(banner);
  console.log(theme.accent('  Simplify. Deploy. Scale.'));
  console.log(theme.muted('  Type \'okik --help\' for more commands.\n'));
}

// Table formatting utilities
export function formatTable(headers: string[], rows: string[][]): void {
  const maxWidths = headers.map((header, i) => 
    Math.max(header.length, ...rows.map(row => row[i]?.length || 0))
  );

  // Print header
  const headerRow = headers.map((header, i) => 
    theme.primary(header.padEnd(maxWidths[i]))
  ).join('  ');
  console.log(headerRow);
  
  // Print separator
  const separator = maxWidths.map(width => 
    theme.muted('─'.repeat(width))
  ).join('  ');
  console.log(separator);
  
  // Print rows
  rows.forEach(row => {
    const formattedRow = row.map((cell, i) => 
      (cell || '').padEnd(maxWidths[i])
    ).join('  ');
    console.log(formattedRow);
  });
}

// Enhanced error formatting
export function formatError(error: Error, context?: string): void {
  console.log(theme.error('\n╭─ Error ─────────────────────────────────────────────╮'));
  console.log(theme.error('│') + ` ${theme.error('✗')} ${error.message}`.padEnd(54) + theme.error('│'));
  
  if (context) {
    console.log(theme.error('│') + ` ${theme.muted('Context:')} ${context}`.padEnd(54) + theme.error('│'));
  }
  
  if (error.stack && process.env.DEBUG) {
    const stackLines = error.stack.split('\n').slice(1, 4);
    stackLines.forEach(line => {
      const truncated = line.length > 50 ? line.substring(0, 47) + '...' : line;
      console.log(theme.error('│') + ` ${theme.muted(truncated)}`.padEnd(54) + theme.error('│'));
    });
  }
  
  console.log(theme.error('╰─────────────────────────────────────────────────────╯\n'));
}

// Progress bar utility
export function createProgressBar(total: number) {
  let current = 0;
  
  return {
    update: (increment: number = 1, message?: string) => {
      current += increment;
      const percentage = Math.round((current / total) * 100);
      const filled = Math.round((current / total) * 30);
      const empty = 30 - filled;
      
      const bar = theme.success('█'.repeat(filled)) + theme.muted('░'.repeat(empty));
      const status = `${bar} ${percentage}%`;
      
      if (message) {
        console.log(`${status} ${theme.muted(message)}`);
      } else {
        process.stdout.write(`\r${status}`);
      }
      
      if (current >= total) {
        console.log(); // New line when complete
      }
    },
    
    complete: (message?: string) => {
      current = total;
      const bar = theme.success('█'.repeat(30));
      console.log(`${bar} 100% ${message ? theme.success(message) : ''}`);
    }
  };
}

// Box formatting
export function printBox(title: string, content: string | string[], options: {
  color?: 'success' | 'error' | 'warning' | 'info' | 'primary';
  width?: number;
} = {}): void {
  const { color = 'info', width = 60 } = options;
  const colorFn = theme[color];
  const lines = Array.isArray(content) ? content : content.split('\n');
  
  // Top border
  console.log(colorFn('╭─' + title + '─'.repeat(Math.max(0, width - title.length - 2)) + '╮'));
  
  // Content
  lines.forEach(line => {
    const paddedLine = line.padEnd(width - 2);
    console.log(colorFn('│') + ` ${paddedLine}` + colorFn('│'));
  });
  
  // Bottom border
  console.log(colorFn('╰' + '─'.repeat(width) + '╯'));
}

export { logger };