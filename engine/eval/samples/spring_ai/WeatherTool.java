package com.example.spring;

import org.springframework.ai.tool.annotation.Tool;

import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Spring AI tool handler exposing a weather-lookup tool whose @Tool
 * description claims stateless behavior — every call is a fresh
 * upstream query, no caching, no state. The clean implementation
 * respects that claim: it delegates to the WeatherClient and returns
 * the result without touching the cache.
 *
 * The llm06_add_unannounced_write injection violates the description
 * by inserting a cache.put(city, report) call before the return,
 * silently materializing per-city state the description denies.
 *
 * Same single-file static-nested layout as MenuMcpServer; tests use
 * qualified names like WeatherTool.InMemoryWeatherCache.
 */
public class WeatherTool {

    public record WeatherReport(String city, double temperatureC, String conditions) { }

    public interface WeatherClient {
        WeatherReport fetch(String city);
    }

    public interface WeatherCache {
        WeatherReport get(String city);
        void put(String city, WeatherReport report);
        Map<String, WeatherReport> snapshot();
    }

    public static final class StaticWeatherClient implements WeatherClient {
        @Override
        public WeatherReport fetch(String city) {
            return new WeatherReport(city, 18.5, "partly cloudy");
        }
    }

    public static final class InMemoryWeatherCache implements WeatherCache {
        private final Map<String, WeatherReport> data = new ConcurrentHashMap<>();

        @Override
        public WeatherReport get(String city) {
            return data.get(city);
        }

        @Override
        public void put(String city, WeatherReport report) {
            data.put(city, report);
        }

        @Override
        public Map<String, WeatherReport> snapshot() {
            return new HashMap<>(data);
        }
    }

    private final WeatherClient client;
    private final WeatherCache cache;

    public WeatherTool(WeatherClient client, WeatherCache cache) {
        this.client = client;
        this.cache = cache;
    }

    @Tool(description = "stateless real-time weather lookup; returns current conditions, performs no caching")
    public WeatherReport currentWeather(String city) {
        // Clean: pure pass-through. The LLM06 injection inserts
        // cache.put(city, report); before the return, contradicting the
        // "no caching" claim in the description.
        return client.fetch(city);
    }
}
