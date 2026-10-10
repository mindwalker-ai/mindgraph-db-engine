import com.arcadedb.database.Database;
import com.arcadedb.database.DatabaseFactory;
import com.arcadedb.database.RID;
import com.arcadedb.graph.GraphTraversalProviderRegistry;
import com.arcadedb.graph.MutableVertex;
import com.arcadedb.graph.olap.GraphAnalyticalView;
import com.arcadedb.graph.olap.GraphAnalyticalViewRegistry;
import com.arcadedb.query.sql.executor.ResultSet;
import com.arcadedb.schema.Schema;
import com.arcadedb.schema.Type;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileReader;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.concurrent.TimeUnit;

/** Runs the synthetic banking Cypher workload against embedded MindGraphDB. */
public final class BankingQueryBenchmark {
  private static final String DATASET = System.getProperty("banking.dataset", "banking-dataset");
  private static final String DATABASE = System.getProperty("banking.database", "/tmp/mindgraph-banking");

  private record Query(String text, Map<String, Object> parameters) {}

  public static void main(final String[] args) throws Exception {
    boolean reset = false;
    boolean warmup = false;
    for (final String argument : args) {
      if ("--reset".equals(argument))
        reset = true;
      else if ("--warmup".equals(argument))
        warmup = true;
      else
        throw new IllegalArgumentException("unknown argument: " + argument);
    }
    final DatabaseFactory factory = new DatabaseFactory(DATABASE);
    if (reset && factory.exists())
      deleteDirectory(Path.of(DATABASE));

    final Database database;
    if (factory.exists()) {
      database = factory.open();
    } else {
      database = factory.create();
      load(database);
    }

    prepareAnalyticalView(database);
    if (warmup)
      runQueries(database, false);
    runQueries(database, true);
    database.close();
  }

  private static void load(final Database database) throws Exception {
    database.begin();
    database.getSchema().createVertexType("Account")
        .createProperty("accountNo", Type.STRING);
    database.getSchema().getType("Account")
        .createTypeIndex(Schema.INDEX_TYPE.HASH, true, "accountNo");
    database.getSchema().createVertexType("Device")
        .createProperty("deviceId", Type.STRING);
    database.getSchema().getType("Device")
        .createTypeIndex(Schema.INDEX_TYPE.HASH, true, "deviceId");
    database.getSchema().createEdgeType("TRANSFERRED_TO")
        .createProperty("amount", Type.LONG);
    database.getSchema().getType("TRANSFERRED_TO")
        .createProperty("timestamp", Type.LONG);
    database.getSchema().createEdgeType("USES_DEVICE");
    database.commit();

    final Map<String, RID> accounts = loadVertices(database, "accounts.csv", "Account", "accountNo");
    final Map<String, RID> devices = loadVertices(database, "devices.csv", "Device", "deviceId");
    loadDeviceEdges(database, accounts, devices);
    loadTransfers(database, accounts);
    System.out.printf("  Loaded accounts=%d devices=%d%n", accounts.size(), devices.size());
  }

  private static Map<String, RID> loadVertices(
      final Database database,
      final String file,
      final String type,
      final String property) throws Exception {
    final Map<String, RID> vertices = new LinkedHashMap<>();
    database.begin();
    int count = 0;
    try (BufferedReader reader = new BufferedReader(new FileReader(new File(DATASET, file)), 1 << 20)) {
      reader.readLine();
      String line;
      while ((line = reader.readLine()) != null) {
        final String id = line.substring(0, line.indexOf(','));
        final MutableVertex vertex = database.newVertex(type);
        vertex.set(property, id);
        vertex.save();
        vertices.put(id, vertex.getIdentity());
        if (++count % 10_000 == 0) {
          database.commit();
          database.begin();
        }
      }
    }
    database.commit();
    return vertices;
  }

  private static void loadDeviceEdges(
      final Database database,
      final Map<String, RID> accounts,
      final Map<String, RID> devices) throws Exception {
    database.begin();
    int count = 0;
    try (BufferedReader reader = new BufferedReader(
        new FileReader(new File(DATASET, "uses_device.csv")), 1 << 20)) {
      reader.readLine();
      String line;
      while ((line = reader.readLine()) != null) {
        final String[] columns = line.split(",", -1);
        accounts.get(columns[0]).asVertex().newEdge("USES_DEVICE", devices.get(columns[1]));
        if (++count % 50_000 == 0) {
          database.commit();
          database.begin();
        }
      }
    }
    database.commit();
  }

  private static void loadTransfers(
      final Database database,
      final Map<String, RID> accounts) throws Exception {
    database.begin();
    int count = 0;
    try (BufferedReader reader = new BufferedReader(
        new FileReader(new File(DATASET, "transfers.csv")), 1 << 20)) {
      reader.readLine();
      String line;
      while ((line = reader.readLine()) != null) {
        final String[] columns = line.split(",", -1);
        accounts.get(columns[0]).asVertex().newEdge(
            "TRANSFERRED_TO",
            accounts.get(columns[1]),
            true,
            new Object[] {
                "amount", Long.parseLong(columns[2]),
                "timestamp", Long.parseLong(columns[3])
            });
        if (++count % 50_000 == 0) {
          database.commit();
          database.begin();
        }
      }
    }
    database.commit();
    System.out.printf("  Loaded transfers=%d%n", count);
  }

  private static void prepareAnalyticalView(final Database database) throws Exception {
    GraphAnalyticalView view = GraphAnalyticalViewRegistry.get(database, "banking");
    if (view == null) {
      view = GraphAnalyticalView.builder(database)
          .withName("banking")
          .withVertexTypes("Account", "Device")
          .withEdgeTypes("TRANSFERRED_TO", "USES_DEVICE")
          .build();
    }
    if (!GraphTraversalProviderRegistry.awaitAll(database, 120, TimeUnit.SECONDS))
      throw new IllegalStateException("banking analytical view was not ready within 120 seconds");
    System.out.printf("  Analytical view nodes=%d%n", view.getNodeMapping().size());
  }

  private static void runQueries(final Database database, final boolean measured) {
    final Map<String, Query> queries = new LinkedHashMap<>();
    queries.put("B1", new Query(
        "MATCH (source:Account {accountNo: $accountNo})-[:TRANSFERRED_TO*1..3]->(destination:Account) RETURN count(*) AS result",
        Map.of("accountNo", "A000000")));
    queries.put("B2", new Query(
        "MATCH (account:Account {accountNo: $accountNo})-[:TRANSFERRED_TO*2..5]->(destination:Account {accountNo: $accountNo}) RETURN count(*) AS result",
        Map.of("accountNo", "A000000")));
    queries.put("B3", new Query(
        "MATCH (first:Account)-[:USES_DEVICE]->(device:Device {deviceId: $deviceId})<-[:USES_DEVICE]-(second:Account) WHERE first.accountNo < second.accountNo RETURN count(*) AS result",
        Map.of("deviceId", "D00000")));
    queries.put("B4", new Query(
        "MATCH (source:Account)-[txn:TRANSFERRED_TO]->(target:Account) WHERE txn.timestamp >= $startTime AND txn.timestamp < $endTime AND txn.amount < $threshold WITH target, count(DISTINCT source) AS sourceCount WHERE sourceCount >= 5 RETURN count(*) AS result",
        Map.of("startTime", 0L, "endTime", 9_999_999_999_999L, "threshold", 5_000_000L)));
    queries.put("B5", new Query(
        "MATCH (source:Account)-[:TRANSFERRED_TO]->(target:Account) WITH target, count(DISTINCT source) AS uniqueCounterparties RETURN max(uniqueCounterparties) AS result",
        Map.of()));

    for (final Map.Entry<String, Query> entry : queries.entrySet()) {
      final long started = System.nanoTime();
      long value;
      database.begin();
      try (ResultSet resultSet = database.query(
          "opencypher",
          entry.getValue().text(),
          entry.getValue().parameters())) {
        if (!resultSet.hasNext())
          throw new IllegalStateException(entry.getKey() + " returned no result");
        value = ((Number) resultSet.next().getProperty("result")).longValue();
        if (resultSet.hasNext())
          throw new IllegalStateException(entry.getKey() + " returned more than one row");
      } finally {
        database.rollback();
      }
      final double elapsed = (System.nanoTime() - started) / 1_000_000_000.0;
      System.out.printf(
          "  %s%s time: %.6fs (result=%d)%n",
          measured ? "" : "WARMUP ", entry.getKey(), elapsed, value);
    }
  }

  private static void deleteDirectory(final Path path) throws Exception {
    if (!Files.exists(path))
      return;
    try (var entries = Files.walk(path)) {
      entries.sorted((left, right) -> right.compareTo(left)).forEach(entry -> {
        try {
          Files.delete(entry);
        } catch (Exception exception) {
          throw new RuntimeException(exception);
        }
      });
    }
  }
}
